import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import defaultdict

from db import (
    init_db, add_record, get_all_records, delete_record,
    update_record, get_record, format_duration, get_records_by_date_range
)

st.set_page_config(page_title="头晕记录", page_icon="📝", layout="wide")

init_db()

ACTION_OPTIONS = ["扭头", "低头", "蹲起", "站立", "躺下", "起床", "跑步", "久坐", "其他"]

if "recording" not in st.session_state:
    st.session_state.recording = False
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None


def start_recording():
    st.session_state.recording = True
    st.session_state.start_time = datetime.now()


def stop_recording():
    st.session_state.recording = False
    st.session_state.start_time = None


# ============== 侧边栏导航 ==============
st.sidebar.title("📝 头晕记录")
page = st.sidebar.radio("导航", ["⏱️ 实时记录", "📊 统计分析", "📋 历史记录", "➕ 新增记录"])


# ============== 实时记录页面 ==============
if page == "⏱️ 实时记录":
    st.title("⏱️ 头晕实时记录")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("计时控制")
        if not st.session_state.recording:
            if st.button("▶️ 开始记录", use_container_width=True, type="primary"):
                start_recording()
                st.rerun()
        else:
            elapsed = datetime.now() - st.session_state.start_time
            st.metric("已记录时长", str(elapsed).split(".")[0])
            if st.button("⏹️ 结束记录", use_container_width=True, type="primary"):
                # 保存记录前先收集信息
                st.session_state.pending_end = True
                st.rerun()

    with col2:
        st.subheader("记录信息")
        if st.session_state.recording and st.session_state.get("pending_end"):
            location = st.text_input("地点", key="end_location")
            actions = st.multiselect("头晕前动作", ACTION_OPTIONS, key="end_actions")
            notes = st.text_area("备注", key="end_notes")

            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("💾 保存记录", use_container_width=True, type="primary"):
                    end_time = datetime.now()
                    add_record(
                        start_time=st.session_state.start_time,
                        end_time=end_time,
                        location=location,
                        actions=actions,
                        notes=notes
                    )
                    st.session_state.pending_end = False
                    stop_recording()
                    st.success("记录已保存！")
                    st.rerun()
            with col_cancel:
                if st.button("❌ 取消", use_container_width=True):
                    st.session_state.pending_end = False
                    st.rerun()
        elif st.session_state.recording:
            st.info("点击「结束记录」后填写详细信息")
        else:
            st.info("点击「开始记录」开始计时")

    # 最近记录
    st.divider()
    st.subheader("最近记录")
    records = get_all_records()[:5]
    if records:
        for r in records:
            with st.container(border=True):
                cols = st.columns([2, 2, 2, 3, 1])
                cols[0].write(f"**开始:** {r['start_time']}")
                cols[1].write(f"**时长:** {format_duration(r['duration_seconds'])}")
                cols[2].write(f"**地点:** {r['location'] or '未填写'}")
                cols[3].write(f"**动作:** {', '.join(r['actions']) if r['actions'] else '无'}")
                cols[4].write(f"**备注:** {r['notes'] or '无'}")
    else:
        st.info("暂无记录")


# ============== 统计分析页面 ==============
if page == "📊 统计分析":
    st.title("📊 统计分析")

    records = get_all_records()
    if not records:
        st.info("暂无数据，请先添加记录")
    else:
        # 视图选择
        view = st.segmented_control("查看维度", ["日", "周", "月", "年"], default="日")

        # 时间范围选择
        col1, col2 = st.columns(2)
        with col1:
            if view == "日":
                selected_date = st.date_input("选择日期", datetime.now().date())
                start = datetime.combine(selected_date, datetime.min.time())
                end = start + timedelta(days=1)
            elif view == "周":
                selected_week = st.date_input("选择周（选该周任意一天）", datetime.now().date())
                monday = selected_week - timedelta(days=selected_week.weekday())
                start = datetime.combine(monday, datetime.min.time())
                end = start + timedelta(days=7)
            elif view == "月":
                selected_month = st.date_input("选择月份（选该月任意一天）", datetime.now().date())
                start = datetime.combine(selected_month.replace(day=1), datetime.min.time())
                if selected_month.month == 12:
                    end = datetime.combine(selected_month.replace(year=selected_month.year + 1, month=1, day=1), datetime.min.time())
                else:
                    end = datetime.combine(selected_month.replace(month=selected_month.month + 1, day=1), datetime.min.time())
            else:  # 年
                selected_year = st.number_input("选择年份", min_value=2000, max_value=2100, value=datetime.now().year)
                start = datetime(selected_year, 1, 1)
                end = datetime(selected_year + 1, 1, 1)

        records = get_records_by_date_range(start, end)

        if not records:
            st.info("该时间段暂无数据")
        else:
            # 统计卡片
            total_count = len(records)
            total_duration = sum(r["duration_seconds"] or 0 for r in records)
            avg_duration = total_duration // total_count if total_count > 0 else 0

            c1, c2, c3 = st.columns(3)
            c1.metric("发作次数", f"{total_count} 次")
            c2.metric("总时长", format_duration(total_duration))
            c3.metric("平均时长", format_duration(avg_duration))

            # 图表数据准备
            if view == "日":
                # 按小时分组柱状图
                hourly_data = defaultdict(int)
                for r in records:
                    t = datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M:%S")
                    hourly_data[t.hour] += r["duration_seconds"] or 0

                df = pd.DataFrame({
                    "小时": list(range(24)),
                    "时长(秒)": [hourly_data.get(h, 0) for h in range(24)]
                })
                df["时长(分钟)"] = df["时长(秒)"] / 60

                fig = px.bar(df, x="小时", y="时长(分钟)",
                             title=f"{selected_date} 各小时头晕时长",
                             labels={"时长(分钟)": "时长（分钟）"},
                             color="时长(分钟)", color_continuous_scale="Reds")
                fig.update_layout(xaxis=dict(tickmode="linear", dtick=1))

            elif view == "周":
                # 按天分组柱状图
                daily_data = defaultdict(int)
                week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                for r in records:
                    t = datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M:%S")
                    daily_data[t.weekday()] += r["duration_seconds"] or 0

                df = pd.DataFrame({
                    "星期": week_days,
                    "时长(秒)": [daily_data.get(i, 0) for i in range(7)]
                })
                df["时长(分钟)"] = df["时长(秒)"] / 60

                fig = px.bar(df, x="星期", y="时长(分钟)",
                             title=f"{start.date()} ~ {(end - timedelta(days=1)).date()} 每周头晕时长",
                             labels={"时长(分钟)": "时长（分钟）"},
                             color="时长(分钟)", color_continuous_scale="Reds")

            elif view == "月":
                # 按天分组的点线图
                daily_data = defaultdict(int)
                for r in records:
                    t = datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M:%S")
                    daily_data[t.day] += r["duration_seconds"] or 0

                days_in_month = (end - start).days
                df = pd.DataFrame({
                    "日期": list(range(1, days_in_month + 1)),
                    "时长(秒)": [daily_data.get(d, 0) for d in range(1, days_in_month + 1)]
                })
                df["时长(分钟)"] = df["时长(秒)"] / 60

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df["日期"], y=df["时长(分钟)"],
                    mode="lines+markers",
                    name="头晕时长",
                    line=dict(color="#e74c3c", width=2),
                    marker=dict(size=8)
                ))
                fig.update_layout(
                    title=f"{start.year}年{start.month}月 每日头晕时长",
                    xaxis_title="日期",
                    yaxis_title="时长（分钟）",
                    xaxis=dict(tickmode="linear", dtick=1)
                )

            else:  # 年
                # 按月分组的点线图
                monthly_data = defaultdict(int)
                for r in records:
                    t = datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M:%S")
                    monthly_data[t.month] += r["duration_seconds"] or 0

                months = ["1月", "2月", "3月", "4月", "5月", "6月",
                          "7月", "8月", "9月", "10月", "11月", "12月"]
                df = pd.DataFrame({
                    "月份": months,
                    "时长(秒)": [monthly_data.get(i, 0) for i in range(1, 13)]
                })
                df["时长(分钟)"] = df["时长(秒)"] / 60

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df["月份"], y=df["时长(分钟)"],
                    mode="lines+markers",
                    name="头晕时长",
                    line=dict(color="#e74c3c", width=2),
                    marker=dict(size=10)
                ))
                fig.update_layout(
                    title=f"{start.year}年 每月头晕时长",
                    xaxis_title="月份",
                    yaxis_title="时长（分钟）"
                )

            st.plotly_chart(fig, use_container_width=True)

            # 详细数据表格
            st.divider()
            st.subheader("详细数据")
            df_display = pd.DataFrame(records)
            df_display["start_time"] = pd.to_datetime(df_display["start_time"])
            df_display["end_time"] = pd.to_datetime(df_display["end_time"], errors="coerce")
            df_display["duration"] = df_display["duration_seconds"].apply(format_duration)
            df_display["actions_str"] = df_display["actions"].apply(lambda x: ", ".join(x) if x else "")
            df_display = df_display.rename(columns={
                "start_time": "开始时间",
                "end_time": "结束时间",
                "duration": "时长",
                "location": "地点",
                "actions_str": "动作",
                "notes": "备注"
            })[["开始时间", "结束时间", "时长", "地点", "动作", "备注"]]
            st.dataframe(df_display, use_container_width=True, hide_index=True)


# ============== 历史记录页面 ==============
if page == "📋 历史记录":
    st.title("📋 历史记录")

    records = get_all_records()
    if not records:
        st.info("暂无历史记录")
    else:
        # 编辑模式
        if st.session_state.edit_id:
            record = get_record(st.session_state.edit_id)
            st.subheader(f"编辑记录 #{record['id']}")

            start_dt = datetime.strptime(record["start_time"], "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(record["end_time"], "%Y-%m-%d %H:%M:%S") if record["end_time"] else None

            col1, col2 = st.columns(2)
            with col1:
                edit_date = st.date_input("日期", start_dt.date(), key="edit_date")
                edit_start = st.time_input("开始时间", start_dt.time(), key="edit_start")
            with col2:
                edit_end_date = st.date_input("结束日期", end_dt.date() if end_dt else start_dt.date(), key="edit_end_date")
                edit_end = st.time_input("结束时间", end_dt.time() if end_dt else start_dt.time(), key="edit_end")

            edit_location = st.text_input("地点", value=record["location"] or "", key="edit_location")
            edit_actions = st.multiselect("头晕前动作", ACTION_OPTIONS, default=record["actions"] or [], key="edit_actions")
            edit_notes = st.text_area("备注", value=record["notes"] or "", key="edit_notes")

            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("💾 保存修改", use_container_width=True, type="primary"):
                    new_start = datetime.combine(edit_date, edit_start)
                    new_end = datetime.combine(edit_end_date, edit_end)
                    if new_end <= new_start:
                        st.error("结束时间必须晚于开始时间")
                    else:
                        update_record(st.session_state.edit_id, new_start, new_end,
                                      edit_location, edit_actions, edit_notes)
                        st.session_state.edit_id = None
                        st.success("修改已保存")
                        st.rerun()
            with col_cancel:
                if st.button("❌ 取消", use_container_width=True):
                    st.session_state.edit_id = None
                    st.rerun()

            st.divider()

        # 记录列表
        for r in records:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                with c1:
                    st.write(f"**开始:** {r['start_time']}")
                    st.write(f"**结束:** {r['end_time'] or '未结束'}")
                with c2:
                    st.write(f"**时长:** {format_duration(r['duration_seconds'])}")
                    st.write(f"**地点:** {r['location'] or '未填写'}")
                with c3:
                    st.write(f"**动作:** {', '.join(r['actions']) if r['actions'] else '无'}")
                    st.write(f"**备注:** {r['notes'] or '无'}")
                with c4:
                    if st.button("✏️ 编辑", key=f"edit_{r['id']}"):
                        st.session_state.edit_id = r["id"]
                        st.rerun()
                    if st.button("🗑️ 删除", key=f"del_{r['id']}"):
                        delete_record(r["id"])
                        st.success("已删除")
                        st.rerun()


# ============== 新增记录页面 ==============
if page == "➕ 新增记录":
    st.title("➕ 手动新增记录")

    with st.form("manual_record"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("日期", datetime.now().date())
            start = st.time_input("开始时间", datetime.now().time())
        with col2:
            end_date = st.date_input("结束日期", datetime.now().date())
            end = st.time_input("结束时间", (datetime.now() + timedelta(minutes=5)).time())

        location = st.text_input("地点")
        actions = st.multiselect("头晕前动作", ACTION_OPTIONS)
        notes = st.text_area("备注")

        submitted = st.form_submit_button("💾 保存记录", use_container_width=True)
        if submitted:
            start_dt = datetime.combine(date, start)
            end_dt = datetime.combine(end_date, end)
            if end_dt <= start_dt:
                st.error("结束时间必须晚于开始时间")
            else:
                add_record(start_dt, end_dt, location, actions, notes)
                st.success("记录已保存！")
