import flet as ft
from datetime import datetime, timedelta
import threading
import time
from collections import defaultdict
import pandas as pd
from db import *

ACTION_OPTIONS = ["扭头", "低头", "蹲起", "站立", "躺下", "起床", "跑步", "久坐", "其他"]


def _build_bar_chart(labels, values, title):
    max_val = max(values) if values else 1
    bars = []
    for label, val in zip(labels, values):
        bar_h = (val / max_val) * 140 if max_val > 0 else 0
        bars.append(
            ft.Column([
                ft.Text(f"{val:.0f}", size=8),
                ft.Container(
                    width=14,
                    height=bar_h,
                    bgcolor=ft.colors.BLUE_400 if val > 0 else ft.colors.GREY_300,
                    border_radius=2,
                ),
                ft.Text(str(label), size=8, text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)
        )
    return ft.Column([
        ft.Text(title, size=12, weight=ft.FontWeight.BOLD),
        ft.Container(
            content=ft.Row(bars, alignment=ft.MainAxisAlignment.SPACE_EVENLY, scroll=ft.ScrollMode.AUTO),
            height=190,
            padding=ft.padding.only(top=4),
        ),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)


def _build_line_chart(labels, values, title):
    max_val = max(values) if values else 1
    chart_h = 160
    chart_w = 300
    n = max(len(values), 1)

    points = []
    for i, val in enumerate(values):
        x = (i / max(n - 1, 1)) * chart_w
        y = chart_h - (val / max_val) * chart_h if max_val > 0 else chart_h
        points.append((x, y, val))

    # 用细条模拟连线 + 圆点
    shapes = []
    for i in range(len(points) - 1):
        x1, y1, _ = points[i]
        x2, y2, _ = points[i + 1]
        # 水平或垂直的阶梯线
        mid_x = (x1 + x2) / 2
        shapes.append(
            ft.Container(width=abs(mid_x - x1), height=2, bgcolor=ft.colors.BLUE_200,
                        left=min(x1, mid_x), top=y1)
        )
        shapes.append(
            ft.Container(width=2, height=abs(y2 - y1), bgcolor=ft.colors.BLUE_200,
                        left=mid_x, top=min(y1, y2))
        )
        shapes.append(
            ft.Container(width=abs(x2 - mid_x), height=2, bgcolor=ft.colors.BLUE_200,
                        left=min(mid_x, x2), top=y2)
        )

    for x, y, _ in points:
        shapes.append(
            ft.Container(width=8, height=8, bgcolor=ft.colors.BLUE_500,
                        border_radius=4, left=x - 4, top=y - 4)
        )

    x_labels_row = ft.Row([
        ft.Text(str(l), size=8, width=chart_w // n, text_align=ft.TextAlign.CENTER)
        for l in labels
    ], width=chart_w)

    return ft.Column([
        ft.Text(title, size=12, weight=ft.FontWeight.BOLD),
        ft.Container(content=ft.Stack(shapes), width=chart_w, height=chart_h),
        x_labels_row,
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)


def render_chart(labels, values, title, _x_label, _y_label, chart_type="bar"):
    if chart_type == "bar":
        return _build_bar_chart(labels, values, title)
    return _build_line_chart(labels, values, title)


def main(page: ft.Page):
    page.title = "头晕记录"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    init_db()

    recording = False
    start_time = None
    timer_thread = None

    content = ft.Column(expand=True)

    def on_nav(e):
        idx = e.control.selected_index
        if idx == 0:
            build_record()
        elif idx == 1:
            build_stats()
        elif idx == 2:
            build_history()
        elif idx == 3:
            build_add()
        page.update()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        on_change=on_nav,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.PLAY_ARROW, label="记录"),
            ft.NavigationBarDestination(icon=ft.Icons.ANALYTICS, label="统计"),
            ft.NavigationBarDestination(icon=ft.Icons.HISTORY, label="历史"),
            ft.NavigationBarDestination(icon=ft.Icons.ADD, label="新增"),
        ],
    )

    def make_action_selector(initial=None):
        selected = set(initial or [])
        label = ft.Text(f"已选: {', '.join(sorted(selected))}" if selected else "头晕前动作: 无")
        checks = []

        def on_change(e, name):
            if e.control.value:
                selected.add(name)
            else:
                selected.discard(name)
            label.value = f"已选: {', '.join(sorted(selected))}" if selected else "头晕前动作: 无"
            page.update()

        for a in ACTION_OPTIONS:
            c = ft.Checkbox(label=a, value=a in selected, on_change=lambda e, name=a: on_change(e, name))
            checks.append(c)

        container = ft.Column([
            label,
            ft.Column(checks, scroll=ft.ScrollMode.AUTO, height=200),
        ])

        def get_value():
            return sorted(selected)

        def set_value(vals):
            nonlocal selected
            selected = set(vals or [])
            label.value = f"已选: {', '.join(sorted(selected))}" if selected else "头晕前动作: 无"
            for c in checks:
                c.value = c.label in selected
            page.update()

        def clear():
            set_value([])

        container.get_value = get_value
        container.set_value = set_value
        container.clear = clear
        return container

    # ==================== 记录页面 ====================
    def build_record():
        nonlocal recording, start_time, timer_thread
        timer_t = ft.Text("00:00:00", size=48, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
        status = ft.Text("点击开始记录头晕", text_align=ft.TextAlign.CENTER)

        loc = ft.TextField(label="地点")
        acts = make_action_selector()
        note = ft.TextField(label="备注", multiline=True, min_lines=2)

        def tick():
            while recording:
                if recording and start_time:
                    s = int((datetime.now() - start_time).total_seconds())
                    h, r = divmod(s, 3600)
                    m, s = divmod(r, 60)
                    new_val = f"{h:02d}:{m:02d}:{s:02d}"

                    def do_update():
                        timer_t.value = new_val
                        page.update()

                    try:
                        if hasattr(page, 'loop') and page.loop:
                            page.loop.call_soon_threadsafe(do_update)
                        else:
                            do_update()
                    except Exception:
                        do_update()
                time.sleep(1)

        def on_start(_):
            nonlocal recording, start_time, timer_thread
            recording, start_time = True, datetime.now()
            status.value = "正在记录..."
            b_start.visible = False
            b_stop.visible = True
            form.visible = False
            timer_thread = threading.Thread(target=tick, daemon=True)
            timer_thread.start()
            page.update()

        def on_stop(_):
            nonlocal recording
            recording = False
            status.value = "请填写信息后保存"
            b_stop.visible = False
            b_save.visible = True
            b_cancel.visible = True
            form.visible = True
            page.update()

        def on_save(_):
            nonlocal recording, start_time
            add_record(start_time, datetime.now(), loc.value, acts.get_value(), note.value)
            recording, start_time = False, None
            timer_t.value = "00:00:00"
            status.value = "记录已保存！"
            b_start.visible = True
            b_stop.visible = False
            b_save.visible = False
            b_cancel.visible = False
            form.visible = False
            loc.value = ""
            acts.clear()
            note.value = ""
            page.update()
            refresh_recent()

        def on_cancel(_):
            nonlocal recording, start_time
            recording, start_time = False, None
            timer_t.value = "00:00:00"
            status.value = "已取消"
            b_start.visible = True
            b_stop.visible = False
            b_save.visible = False
            b_cancel.visible = False
            form.visible = False
            page.update()

        b_start = ft.ElevatedButton(
            "开始记录", icon=ft.Icons.PLAY_ARROW, on_click=on_start,
            bgcolor=ft.Colors.GREEN, color=ft.Colors.WHITE, width=200,
        )
        b_stop = ft.ElevatedButton(
            "结束记录", icon=ft.Icons.STOP, on_click=on_stop,
            bgcolor=ft.Colors.RED, color=ft.Colors.WHITE, width=200, visible=False,
        )
        b_save = ft.ElevatedButton("保存", icon=ft.Icons.SAVE, on_click=on_save, width=120, visible=False)
        b_cancel = ft.ElevatedButton("取消", icon=ft.Icons.CANCEL, on_click=on_cancel, width=120, visible=False)
        form = ft.Column(
            [loc, acts, note, ft.Row([b_save, b_cancel], alignment=ft.MainAxisAlignment.CENTER)],
            visible=False,
        )

        recent = ft.Column(scroll=ft.ScrollMode.AUTO, height=200)

        def refresh_recent():
            recent.controls.clear()
            for r in get_all_records()[:5]:
                recent.controls.append(
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Text(r["start_time"], weight=ft.FontWeight.BOLD),
                                ft.Text(f"时长: {format_duration(r['duration_seconds'])}"),
                                ft.Text(f"地点: {r['location'] or '未填写'}"),
                                ft.Text(f"动作: {', '.join(r['actions']) if r['actions'] else '无'}"),
                            ], spacing=4),
                            padding=12,
                        )
                    )
                )
            page.update()

        refresh_recent()

        content.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Container(height=30),
                    timer_t,
                    status,
                    ft.Row([b_start, b_stop], alignment=ft.MainAxisAlignment.CENTER),
                    form,
                    ft.Divider(),
                    ft.Text("最近记录", weight=ft.FontWeight.BOLD, size=18),
                    recent,
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO),
                padding=16,
                expand=True,
                alignment=ft.alignment.top_center,
            )
        ]

    # ==================== 统计页面 ====================
    def build_stats():
        view_dd = ft.Dropdown(
            label="维度", value="日", width=100,
            options=[ft.dropdown.Option(v) for v in ["日", "周", "月", "年"]],
        )

        dp = ft.DatePicker(value=datetime.now().date())
        page.overlay.append(dp)
        date_lbl = ft.Text("今天")

        def on_pick(_):
            if dp.value:
                date_lbl.value = dp.value.strftime("%Y-%m-%d")
                page.update()

        dp.on_change = on_pick

        c_txt = ft.Text("0", size=32, weight=ft.FontWeight.BOLD)
        t_txt = ft.Text("0", size=32, weight=ft.FontWeight.BOLD)
        a_txt = ft.Text("0", size=32, weight=ft.FontWeight.BOLD)
        chart_box = ft.Container(expand=True)
        tbl_box = ft.Container()

        def analyze(_):
            v = view_dd.value
            d = dp.value or datetime.now().date()

            if v == "日":
                s = datetime.combine(d, datetime.min.time())
                e = s + timedelta(days=1)
            elif v == "周":
                m = d - timedelta(days=d.weekday())
                s = datetime.combine(m, datetime.min.time())
                e = s + timedelta(days=7)
            elif v == "月":
                s = datetime.combine(d.replace(day=1), datetime.min.time())
                nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
                e = datetime.combine(nxt, datetime.min.time())
            else:
                s = datetime(d.year, 1, 1)
                e = datetime(d.year + 1, 1, 1)

            recs = get_records_by_date_range(s, e)
            if not recs:
                c_txt.value = "0"
                t_txt.value = "0"
                a_txt.value = "0"
                chart_box.content = ft.Text("暂无数据", text_align=ft.TextAlign.CENTER)
                tbl_box.content = ft.Text("")
                page.update()
                return

            cnt = len(recs)
            tot = sum(r["duration_seconds"] or 0 for r in recs)
            avg = tot // cnt
            c_txt.value = str(cnt)
            t_txt.value = format_duration(tot)
            a_txt.value = format_duration(avg)

            if v == "日":
                h = defaultdict(int)
                for r in recs:
                    t = datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M:%S")
                    h[t.hour] += r["duration_seconds"] or 0
                labels = [f"{i}时" for i in range(24)]
                values = [h.get(i, 0) / 60 for i in range(24)]
                chart_box.content = render_chart(labels, values, f"{s.date()} 各小时时长", "", "", "bar")
            elif v == "周":
                h = defaultdict(int)
                wd = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                for r in recs:
                    t = datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M:%S")
                    h[t.weekday()] += r["duration_seconds"] or 0
                values = [h.get(i, 0) / 60 for i in range(7)]
                chart_box.content = render_chart(wd, values, "每周时长", "", "", "line")
            elif v == "月":
                h = defaultdict(int)
                for r in recs:
                    t = datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M:%S")
                    h[t.day] += r["duration_seconds"] or 0
                days = (e - s).days
                labels = [str(i) for i in range(1, days + 1)]
                values = [h.get(i, 0) / 60 for i in range(1, days + 1)]
                chart_box.content = render_chart(labels, values, f"{s.year}年{s.month}月 每日时长", "", "", "line")
            else:
                h = defaultdict(int)
                for r in recs:
                    t = datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M:%S")
                    h[t.month] += r["duration_seconds"] or 0
                labels = [f"{i}月" for i in range(1, 13)]
                values = [h.get(i, 0) / 60 for i in range(1, 13)]
                chart_box.content = render_chart(labels, values, f"{s.year}年 每月时长", "", "", "line")

            dd = pd.DataFrame(recs)
            dd["duration"] = dd["duration_seconds"].apply(format_duration)
            dd["actions_str"] = dd["actions"].apply(lambda x: ", ".join(x) if x else "")
            dd = dd[["start_time", "end_time", "duration", "location", "actions_str", "notes"]]
            dd.columns = ["开始时间", "结束时间", "时长", "地点", "动作", "备注"]
            rows = [
                ft.DataRow(cells=[ft.DataCell(ft.Text(str(v))) for v in row])
                for _, row in dd.iterrows()
            ]
            tbl_box.content = ft.Column([
                ft.DataTable(
                    columns=[ft.DataColumn(ft.Text(c)) for c in dd.columns],
                    rows=rows,
                )
            ], scroll=ft.ScrollMode.AUTO)
            page.update()

        analyze_btn = ft.ElevatedButton("分析", icon=ft.Icons.ANALYTICS, on_click=analyze)

        content.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Container(height=30),
                    ft.Row([
                        view_dd,
                        ft.ElevatedButton("选日期", icon=ft.Icons.CALENDAR_TODAY, on_click=lambda _: page.open(dp)),
                        date_lbl,
                        analyze_btn,
                    ], wrap=True),
                    ft.Divider(),
                    ft.Row([
                        ft.Card(content=ft.Container(
                            content=ft.Column([ft.Text("发作次数"), c_txt], alignment=ft.CrossAxisAlignment.CENTER),
                            padding=16,
                        )),
                        ft.Card(content=ft.Container(
                            content=ft.Column([ft.Text("总时长"), t_txt], alignment=ft.CrossAxisAlignment.CENTER),
                            padding=16,
                        )),
                        ft.Card(content=ft.Container(
                            content=ft.Column([ft.Text("平均时长"), a_txt], alignment=ft.CrossAxisAlignment.CENTER),
                            padding=16,
                        )),
                    ], alignment=ft.MainAxisAlignment.SPACE_EVENLY),
                    ft.Divider(),
                    chart_box,
                    ft.Divider(),
                    ft.Text("详细数据", weight=ft.FontWeight.BOLD),
                    tbl_box,
                ], scroll=ft.ScrollMode.AUTO),
                padding=16,
                expand=True,
            )
        ]
        analyze(None)

    # ==================== 历史页面 ====================
    def build_history():
        list_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

        def refresh():
            list_col.controls.clear()
            recs = get_all_records()
            if not recs:
                list_col.controls.append(ft.Text("暂无记录"))
            for r in recs:
                def edit_handler(rid):
                    return lambda _: do_edit(rid)

                def del_handler(rid):
                    return lambda _: do_del(rid)

                list_col.controls.append(
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Text(f"开始: {r['start_time']}", weight=ft.FontWeight.BOLD),
                                ft.Text(f"结束: {r['end_time'] or '未结束'}"),
                                ft.Text(f"时长: {format_duration(r['duration_seconds'])}"),
                                ft.Text(f"地点: {r['location'] or '未填写'}"),
                                ft.Text(f"动作: {', '.join(r['actions']) if r['actions'] else '无'}"),
                                ft.Text(f"备注: {r['notes'] or '无'}"),
                                ft.Row([
                                    ft.TextButton("编辑", icon=ft.Icons.EDIT, on_click=edit_handler(r["id"])),
                                    ft.TextButton("删除", icon=ft.Icons.DELETE, on_click=del_handler(r["id"])),
                                ], alignment=ft.MainAxisAlignment.END),
                            ], spacing=4),
                            padding=12,
                        )
                    )
                )
            page.update()

        def do_del(rid):
            def yes(_):
                delete_record(rid)
                page.close(dlg)
                refresh()

            dlg = ft.AlertDialog(
                title=ft.Text("确认删除"),
                content=ft.Text("确定删除这条记录？"),
                actions=[
                    ft.TextButton("取消", on_click=lambda _: page.close(dlg)),
                    ft.TextButton("删除", on_click=yes),
                ],
            )
            page.open(dlg)

        def do_edit(rid):
            rec = get_record(rid)
            if not rec:
                return
            st = datetime.strptime(rec["start_time"], "%Y-%m-%d %H:%M:%S")
            en = datetime.strptime(rec["end_time"], "%Y-%m-%d %H:%M:%S") if rec["end_time"] else st

            s_d = ft.DatePicker(value=st.date())
            s_t = ft.TimePicker(value=st.time())
            e_d = ft.DatePicker(value=en.date())
            e_t = ft.TimePicker(value=en.time())
            page.overlay.extend([s_d, s_t, e_d, e_t])

            s_d_l = ft.Text(st.strftime("%Y-%m-%d"))
            s_t_l = ft.Text(st.strftime("%H:%M"))
            e_d_l = ft.Text(en.strftime("%Y-%m-%d"))
            e_t_l = ft.Text(en.strftime("%H:%M"))

            s_d.on_change = lambda e: setattr(s_d_l, "value", e.control.value.strftime("%Y-%m-%d")) or page.update()
            s_t.on_change = lambda e: setattr(s_t_l, "value", e.control.value.strftime("%H:%M")) or page.update()
            e_d.on_change = lambda e: setattr(e_d_l, "value", e.control.value.strftime("%Y-%m-%d")) or page.update()
            e_t.on_change = lambda e: setattr(e_t_l, "value", e.control.value.strftime("%H:%M")) or page.update()

            loc = ft.TextField(label="地点", value=rec["location"] or "")
            acts = make_action_selector(rec["actions"] or [])
            note = ft.TextField(label="备注", value=rec["notes"] or "", multiline=True)

            def save(_):
                ns = datetime.combine(s_d.value, s_t.value) if s_d.value and s_t.value else st
                ne = datetime.combine(e_d.value, e_t.value) if e_d.value and e_t.value else en
                if ne <= ns:
                    page.open(ft.SnackBar(ft.Text("结束时间必须晚于开始时间")))
                    return
                update_record(rid, ns, ne, loc.value, acts.get_value(), note.value)
                page.close(dlg)
                refresh()

            dlg = ft.AlertDialog(
                title=ft.Text(f"编辑 #{rid}"),
                content=ft.Column([
                    ft.Row([ft.ElevatedButton("开始日期", on_click=lambda _: page.open(s_d)), s_d_l]),
                    ft.Row([ft.ElevatedButton("开始时间", on_click=lambda _: page.open(s_t)), s_t_l]),
                    ft.Row([ft.ElevatedButton("结束日期", on_click=lambda _: page.open(e_d)), e_d_l]),
                    ft.Row([ft.ElevatedButton("结束时间", on_click=lambda _: page.open(e_t)), e_t_l]),
                    loc, acts, note,
                ], tight=True, scroll=ft.ScrollMode.AUTO),
                actions=[
                    ft.TextButton("取消", on_click=lambda _: page.close(dlg)),
                    ft.TextButton("保存", on_click=save),
                ],
            )
            page.open(dlg)

        refresh()
        content.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Container(height=30),
                    ft.Text("历史记录", weight=ft.FontWeight.BOLD, size=20),
                    list_col,
                ], expand=True),
                padding=16,
                expand=True,
            )
        ]

    # ==================== 新增页面 ====================
    def build_add():
        s_d = ft.DatePicker()
        s_t = ft.TimePicker()
        e_d = ft.DatePicker()
        e_t = ft.TimePicker()
        page.overlay.extend([s_d, s_t, e_d, e_t])

        s_d_l = ft.Text("未选择")
        s_t_l = ft.Text("未选择")
        e_d_l = ft.Text("未选择")
        e_t_l = ft.Text("未选择")

        s_d.on_change = lambda e: setattr(s_d_l, "value", e.control.value.strftime("%Y-%m-%d")) or page.update()
        s_t.on_change = lambda e: setattr(s_t_l, "value", e.control.value.strftime("%H:%M")) or page.update()
        e_d.on_change = lambda e: setattr(e_d_l, "value", e.control.value.strftime("%Y-%m-%d")) or page.update()
        e_t.on_change = lambda e: setattr(e_t_l, "value", e.control.value.strftime("%H:%M")) or page.update()

        loc = ft.TextField(label="地点")
        acts = make_action_selector()
        note = ft.TextField(label="备注", multiline=True, min_lines=2)

        def save(_):
            if not (s_d.value and s_t.value and e_d.value and e_t.value):
                page.open(ft.SnackBar(ft.Text("请选择完整的时间")))
                return
            st = datetime.combine(s_d.value, s_t.value)
            en = datetime.combine(e_d.value, e_t.value)
            if en <= st:
                page.open(ft.SnackBar(ft.Text("结束时间必须晚于开始时间")))
                return
            add_record(st, en, loc.value, acts.get_value(), note.value)
            page.open(ft.SnackBar(ft.Text("记录已保存！")))
            s_d.value = None
            s_t.value = None
            e_d.value = None
            e_t.value = None
            s_d_l.value = "未选择"
            s_t_l.value = "未选择"
            e_d_l.value = "未选择"
            e_t_l.value = "未选择"
            loc.value = ""
            acts.clear()
            note.value = ""
            page.update()

        content.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Container(height=30),
                    ft.Text("手动新增", weight=ft.FontWeight.BOLD, size=20),
                    ft.Text("开始时间", weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.ElevatedButton("日期", icon=ft.Icons.CALENDAR_TODAY, on_click=lambda _: page.open(s_d)),
                        s_d_l,
                    ]),
                    ft.Row([
                        ft.ElevatedButton("时间", icon=ft.Icons.ACCESS_TIME, on_click=lambda _: page.open(s_t)),
                        s_t_l,
                    ]),
                    ft.Text("结束时间", weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.ElevatedButton("日期", icon=ft.Icons.CALENDAR_TODAY, on_click=lambda _: page.open(e_d)),
                        e_d_l,
                    ]),
                    ft.Row([
                        ft.ElevatedButton("时间", icon=ft.Icons.ACCESS_TIME, on_click=lambda _: page.open(e_t)),
                        e_t_l,
                    ]),
                    loc,
                    acts,
                    note,
                    ft.ElevatedButton(
                        "保存", icon=ft.Icons.SAVE, on_click=save,
                        bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE, width=200,
                    ),
                ], scroll=ft.ScrollMode.AUTO),
                padding=16,
                expand=True,
            )
        ]

    # 初始显示记录页面
    build_record()
    page.add(content)


ft.app(target=main)
