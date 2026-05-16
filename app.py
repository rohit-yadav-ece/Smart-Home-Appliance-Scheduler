"""
Smart Home Appliance Scheduler — Interactive Dashboard
Run: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scheduler import (
    Task, SmartHomeScheduler, PriorityScheduler,
    DependencyGraph, PowerPathOptimizer
)

st.set_page_config(page_title="Smart Home Scheduler", page_icon="🏠", layout="wide")

st.title("🏠 Smart Home Appliance Scheduler")
st.markdown("**DSA-driven IoT scheduler** — Min-Heap · Dijkstra · BFS/DFS · Greedy Interval Scheduling")
st.markdown("---")

# Sidebar
st.sidebar.header("⚙️ Configuration")
peak_budget = st.sidebar.slider("Peak Power Budget (Watts)", 1000, 8000, 3500, step=500)
st.sidebar.markdown("---")
st.sidebar.markdown("**Algorithm Complexity**")
st.sidebar.markdown("- Min-Heap insert: `O(log n)`")
st.sidebar.markdown("- BFS / DFS: `O(V + E)`")
st.sidebar.markdown("- Dijkstra: `O((V+E) log V)`")
st.sidebar.markdown("- Greedy Interval: `O(n log n)`")
st.sidebar.markdown("---")
st.sidebar.markdown("[GitHub Repo ↗](https://github.com/rohit-yadav-ece/Smart-Home-Appliance-Scheduler)")

# Default tasks
default_tasks = [
    ("T1", "WashingMachine",  2000,  60, 7,  600,  900, ""),
    ("T2", "Dishwasher",      1500,  90, 5,  660, 1080, "T1"),
    ("T3", "WaterHeater",     2500,  30, 9,  360,  480, ""),
    ("T4", "AirConditioner",  1800, 120, 6,  720, 1200, ""),
    ("T5", "OvenMicrowave",   1200,  20, 8, 1080, 1140, ""),
    ("T6", "EV_Charger",      3000, 240, 4,    0,  360, ""),
    ("T7", "PoolPump",         800, 180, 3,  480, 1200, ""),
    ("T8", "Iron",             900,  15, 7,  540,  600, ""),
]

df_input = pd.DataFrame(default_tasks, columns=[
    "ID", "Device", "Power (W)", "Duration (min)",
    "Urgency", "Earliest Start (min)", "Deadline (min)", "Depends On"
])

# Tab layout
tab1, tab2, tab3, tab4 = st.tabs(["📋 Tasks", "📊 Schedule Results", "📈 Power Timeline", "🧠 How It Works"])

with tab1:
    st.subheader("Task Input")
    edited_df = st.data_editor(df_input, num_rows="dynamic", use_container_width=True)
    st.caption("💡 Edit values directly. Times are in minutes from 00:00 (e.g., 600 = 10:00 AM).")

with tab2:
    if st.button("🚀 Run Scheduler", type="primary"):
        scheduler = SmartHomeScheduler(peak_power_budget=peak_budget)
        for _, row in edited_df.iterrows():
            deps = [d.strip() for d in row["Depends On"].split(",") if d.strip()]
            task = Task(
                priority_score=0,
                task_id=row["ID"],
                device=row["Device"],
                power_watts=float(row["Power (W)"]),
                duration_min=int(row["Duration (min)"]),
                urgency=int(row["Urgency"]),
                earliest_start=int(row["Earliest Start (min)"]),
                deadline=int(row["Deadline (min)"]),
                dependencies=deps,
            )
            scheduler.add_task(task)

        result = scheduler.run()

        if "error" in result:
            st.error(result["error"])
        else:
            # Metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("✅ Scheduled", result["total_scheduled"])
            c2.metric("⛔ Rejected", result["total_rejected"])
            c3.metric("📉 Peak Before", f"{result['peak_power_before_W']} W")
            c4.metric("⚡ Peak After", f"{result['peak_power_after_W']} W",
                      delta=f"-{result['peak_reduction_pct']}%", delta_color="inverse")

            # Schedule table
            st.subheader("📅 Final Schedule")
            sched_rows = []
            for start, end, task in scheduler.interval_scheduler.schedule:
                sched_rows.append({
                    "Task": task.task_id,
                    "Device": task.device,
                    "Start (min)": start,
                    "Start (HH:MM)": f"{start//60:02d}:{start%60:02d}",
                    "End (HH:MM)": f"{end//60:02d}:{end%60:02d}",
                    "Power (W)": task.power_watts,
                    "Urgency": task.urgency,
                })
            sched_df = pd.DataFrame(sched_rows)
            st.dataframe(sched_df, use_container_width=True)

            # Gantt chart
            st.subheader("📊 Gantt Chart — Device Execution Timeline")
            gantt_rows = []
            for start, end, task in scheduler.interval_scheduler.schedule:
                gantt_rows.append({
                    "Device": task.device,
                    "Start": pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=start),
                    "End":   pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=end),
                    "Power": task.power_watts,
                })
            gantt_df = pd.DataFrame(gantt_rows)
            fig_gantt = px.timeline(gantt_df, x_start="Start", x_end="End", y="Device",
                                    color="Power", color_continuous_scale="Viridis")
            fig_gantt.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_gantt, use_container_width=True)
            st.session_state["last_result"] = (scheduler, result)
    else:
        st.info("👆 Click 'Run Scheduler' to compute the optimal schedule.")

with tab3:
    st.subheader("📈 Power Consumption Over the Day")
    if "last_result" in st.session_state:
        scheduler, result = st.session_state["last_result"]
        usage = scheduler.interval_scheduler.power_usage
        timeline = pd.DataFrame({
            "Minute": list(range(1440)),
            "Time": [f"{m//60:02d}:{m%60:02d}" for m in range(1440)],
            "Power (W)": [usage.get(m, 0) for m in range(1440)],
        })
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=timeline["Minute"], y=timeline["Power (W)"],
                                 fill='tozeroy', name='Power Usage',
                                 line=dict(color='#2E86AB')))
        fig.add_hline(y=peak_budget, line_dash="dash", line_color="red",
                      annotation_text=f"Peak Budget: {peak_budget} W")
        fig.update_layout(xaxis_title="Minute of Day (0–1440)", yaxis_title="Power (W)",
                          height=400, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("⚡ Peak Reached", f"{max(usage.values()) if usage else 0:.0f} W")
        c2.metric("🎯 Budget Limit", f"{peak_budget} W")
        c3.metric("✅ Within Budget", "Yes" if (max(usage.values()) if usage else 0) <= peak_budget else "No")
    else:
        st.info("Run the scheduler first (on the 📊 tab) to see the power timeline.")

with tab4:
    st.subheader("🧠 How the 4 Algorithms Work Together")
    st.markdown("""
### 1️⃣ Min-Heap Priority Queue — `O(log n)` insertion
Tasks are pushed onto a min-heap keyed by `priority_score = -(urgency × 10) + slack`.
Most-urgent and least-slack tasks bubble to the top automatically.

### 2️⃣ BFS / DFS — Dependency Graph
- **BFS** computes the level (distance) of each dependent device.
- **DFS** detects cycles — a cycle means the schedule is infeasible.
- **Kahn's topological sort** produces a valid execution order.

### 3️⃣ Dijkstra's Algorithm — Power-Cost Optimal Path
For appliances with multiple operating modes (e.g., AC: Eco → Normal → Boost),
Dijkstra finds the lowest-power-cost transition path between states.

### 4️⃣ Greedy Interval Scheduling — Peak-Power Reduction
Tasks are sorted by Earliest Deadline First (EDF), then placed greedily
in the earliest time slot that keeps the cumulative power under the budget.
This consistently reduces peak load by 20–75% in benchmark scenarios.
    """)

st.markdown("---")
st.caption("Built with ❤️ by Rohit Yadav · B.Tech ECE · BIT Mesra · github.com/rohit-yadav-ece")
