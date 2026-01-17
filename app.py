import datetime as dt
import math
from typing import Dict, Tuple

import altair as alt
import pandas as pd
import streamlit as st


st.set_page_config(page_title="Nexus", layout="wide")

st.markdown(
    """
<style>
:root {
  --bg: #0b0c10;
  --panel: #11151c;
  --panel-strong: #151a22;
  --text: #e6e6e6;
  --muted: #9aa4b2;
  --accent: #00d4ff;
  --accent-2: #ffb020;
  --danger: #ff4d4d;
  --ok: #2ecc71;
}

.stApp {
  background: radial-gradient(circle at 18% 8%, #17202a 0%, #0b0c10 52%, #07080b 100%);
  color: var(--text);
  font-family: "SF Pro Display", "Avenir Next", "Helvetica Neue", sans-serif;
}

section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0f141b 0%, #0b0c10 100%);
  border-right: 1px solid #1f2732;
}

h1, h2, h3, h4 {
  color: var(--text);
  letter-spacing: 0.3px;
}

.stMetric {
  background: var(--panel);
  border: 1px solid #1f2732;
  border-radius: 12px;
  padding: 12px;
}

div[data-testid="stMetricValue"] {
  color: var(--accent);
  font-weight: 700;
}

div[data-testid="stMetricDelta"] {
  color: var(--muted);
}

div[data-testid="stMarkdownContainer"] > p {
  color: var(--muted);
}
</style>
""",
    unsafe_allow_html=True,
)


SHARED_TASKS = [
    ("M5 Chip", 30, [], "component"),
    ("Neural Accelerator", 25, [], "component"),
    ("Liquid Glass Display", 28, [], "component"),
]

PRODUCT_CONFIGS = {
    "MacBook Pro": {
        "margin_rank": 1,
        "unique_tasks": [
            ("Thermal System", 18, ["M5 Chip"], "component"),
            ("macOS M5 Optimization", 24, ["M5 Chip"], "software"),
        ],
    },
    "iPad Pro": {
        "margin_rank": 2,
        "unique_tasks": [
            ("M5-optimized iPadOS", 20, ["M5 Chip"], "software"),
            ("Pencil Pro Calibration", 12, ["Liquid Glass Display"], "component"),
        ],
    },
    "Vision Pro": {
        "margin_rank": 3,
        "unique_tasks": [
            ("R1 Sensor", 22, [], "component"),
            ("VisionOS Spatial UX", 26, ["M5 Chip", "R1 Sensor"], "software"),
        ],
    },
}


def compute_allocation_delays(yield_percent: int) -> Dict[str, int]:
    if yield_percent >= 70:
        return {product: 0 for product in PRODUCT_CONFIGS}

    shortage_factor = (70 - yield_percent) / 70
    base_delay = int(math.ceil(shortage_factor * 28))
    return {
        "MacBook Pro": 0,
        "iPad Pro": base_delay,
        "Vision Pro": base_delay + 7,
    }


def build_product_tasks(product_name: str) -> Dict[str, dict]:
    tasks = {}
    for name, duration, deps, task_type in SHARED_TASKS:
        tasks[name] = {
            "duration": duration,
            "deps": list(deps),
            "type": task_type,
        }

    for name, duration, deps, task_type in PRODUCT_CONFIGS[product_name]["unique_tasks"]:
        tasks[name] = {
            "duration": duration,
            "deps": list(deps),
            "type": task_type,
        }

    component_tasks = [task for task, meta in tasks.items() if meta["type"] == "component"]
    software_tasks = [task for task, meta in tasks.items() if meta["type"] == "software"]

    tasks["Factory Build"] = {
        "duration": 14,
        "deps": component_tasks,
        "type": "factory",
    }
    tasks["Validation & Launch Readiness"] = {
        "duration": 10,
        "deps": ["Factory Build"] + software_tasks,
        "type": "validation",
    }
    tasks["Ship"] = {
        "duration": 0,
        "deps": ["Validation & Launch Readiness"],
        "type": "milestone",
    }
    return tasks


def apply_constraints(
    tasks: Dict[str, dict],
    product_name: str,
    yield_percent: int,
    throughput: int,
    bug_count: int,
) -> Tuple[Dict[str, dict], Dict[str, int], int]:
    allocation_delays = compute_allocation_delays(yield_percent)
    factory_multiplier = 100 / max(1, throughput)
    bug_delay = int(math.ceil(bug_count / 12))
    na_delay = int(math.ceil(max(0, 90 - throughput) / 10)) * 2

    updated = {}
    for task_name, meta in tasks.items():
        duration = meta["duration"]
        if meta["type"] == "factory":
            duration = math.ceil(duration * factory_multiplier)
        if meta["type"] == "software":
            duration += bug_delay
        if task_name == "Neural Accelerator":
            duration += na_delay
        if task_name == "M5 Chip":
            duration += allocation_delays.get(product_name, 0)

        updated[task_name] = {
            **meta,
            "duration": max(0, int(duration)),
        }

    return updated, allocation_delays, na_delay


def compute_cpm(tasks: Dict[str, dict]) -> Tuple[Dict[str, int], Dict[str, int]]:
    remaining = {task: set(meta["deps"]) for task, meta in tasks.items()}
    order = []

    while remaining:
        ready = [task for task, deps in remaining.items() if not deps]
        if not ready:
            raise ValueError("Dependency cycle detected in tasks.")
        for task in sorted(ready):
            order.append(task)
            del remaining[task]
            for deps in remaining.values():
                deps.discard(task)

    earliest_start = {}
    earliest_finish = {}
    for task in order:
        deps = tasks[task]["deps"]
        start = max((earliest_finish[dep] for dep in deps), default=0)
        finish = start + tasks[task]["duration"]
        earliest_start[task] = start
        earliest_finish[task] = finish

    return earliest_start, earliest_finish


def build_schedule(
    product_name: str,
    start_date: dt.date,
    yield_percent: int,
    throughput: int,
    bug_count: int,
):
    base_tasks = build_product_tasks(product_name)
    tasks, allocation_delays, na_delay = apply_constraints(
        base_tasks,
        product_name,
        yield_percent,
        throughput,
        bug_count,
    )
    earliest_start, earliest_finish = compute_cpm(tasks)

    task_rows = []
    for task, meta in tasks.items():
        task_rows.append(
            {
                "product": product_name,
                "task": task,
                "start": start_date + dt.timedelta(days=earliest_start[task]),
                "end": start_date + dt.timedelta(days=earliest_finish[task]),
                "duration": meta["duration"],
                "type": meta["type"],
            }
        )

    schedule = pd.DataFrame(task_rows)
    ship_days = earliest_finish["Ship"]
    ship_date = start_date + dt.timedelta(days=ship_days)

    return schedule, ship_date, ship_days, allocation_delays, na_delay


def confidence_score(yield_percent: int, throughput: int, bug_count: int, delay_days: int) -> int:
    score = 100
    if yield_percent < 70:
        score -= (70 - yield_percent) * 1.2 + 10
    else:
        score -= max(0, 85 - yield_percent) * 0.4

    score -= max(0, 100 - throughput) * 0.4
    score -= bug_count * 0.2
    score -= max(0, delay_days) * 0.5
    return max(0, min(100, int(round(score))))


def confidence_band(score: int) -> Tuple[str, str]:
    if score >= 80:
        return "Green", "#2ecc71"
    if score >= 55:
        return "Yellow", "#f1c40f"
    return "Red", "#e74c3c"


st.title("Nexus: M5 Launch Readiness Simulator")
st.caption(
    "Model how supply constraints cascade across MacBook Pro, iPad Pro, and Vision Pro launch windows."
)

with st.sidebar:
    st.header("Constraint Sliders")
    yield_percent = st.slider("M5 Chip Yield (%)", 40, 100, 85, 1)
    throughput = st.slider("Factory Throughput (%)", 60, 120, 100, 1)
    bug_count = st.slider("Software Stability (Open Bugs)", 0, 200, 45, 1)
    start_date = st.date_input("Program Start Date", dt.date.today())

baseline_yield = 85
baseline_throughput = 100
baseline_bug_count = 25

baseline = {}
current = {}
logs = []
allocation_snapshot = compute_allocation_delays(yield_percent)

for product in PRODUCT_CONFIGS:
    _, _, baseline_days, _, _ = build_schedule(
        product, start_date, baseline_yield, baseline_throughput, baseline_bug_count
    )
    schedule, ship_date, ship_days, _, na_delay = build_schedule(
        product, start_date, yield_percent, throughput, bug_count
    )
    baseline[product] = baseline_days
    current[product] = {
        "schedule": schedule,
        "ship_date": ship_date,
        "ship_days": ship_days,
        "delay_days": ship_days - baseline_days,
        "na_delay": na_delay,
    }

if yield_percent < 70:
    if allocation_snapshot["iPad Pro"] > 0:
        logs.append(
            f"Warning: M5 chip yield below 70%; iPad Pro launch pushed by {allocation_snapshot['iPad Pro']} days."
        )
    if allocation_snapshot["Vision Pro"] > 0:
        logs.append(
            f"Warning: M5 chip yield below 70%; Vision Pro launch pushed by {allocation_snapshot['Vision Pro']} days."
        )
    logs.append("Action: Prioritized MacBook Pro allocation to protect revenue.")

if throughput < 85:
    na_delay = current["Vision Pro"]["na_delay"]
    if na_delay > 0:
        logs.append(
            f"Warning: Neural Accelerator throughput constraint adds {na_delay} days; Vision Pro launch pushed by {current['Vision Pro']['delay_days']} days."
        )
    logs.append("Risk: Factory throughput below 85% is elongating final assembly.")

if bug_count > 90:
    logs.append(
        f"Risk: Software stability degraded ({bug_count} open bugs); shift QA staffing to reduce launch exposure."
    )

if not logs:
    logs.append("On track: No critical constraints detected; launch windows remain within baseline.")

metric_cols = st.columns(3)
for idx, product in enumerate(PRODUCT_CONFIGS):
    ship_date = current[product]["ship_date"]
    delay_days = current[product]["delay_days"]
    metric_cols[idx].metric(
        f"{product} Earliest Ship",
        ship_date.strftime("%Y-%m-%d"),
        f"{delay_days:+d} days vs baseline",
    )

gantt_rows = []
for product in PRODUCT_CONFIGS:
    gantt_rows.append(
        {
            "Product": product,
            "Start": start_date,
            "End": current[product]["ship_date"],
            "Ship Date": current[product]["ship_date"].strftime("%Y-%m-%d"),
        }
    )

gantt_df = pd.DataFrame(gantt_rows)
gantt_chart = (
    alt.Chart(gantt_df)
    .mark_bar(cornerRadius=6)
    .encode(
        x=alt.X("Start:T", title=""),
        x2="End:T",
        y=alt.Y("Product:N", title="", sort=list(PRODUCT_CONFIGS.keys())),
        color=alt.Color(
            "Product:N",
            scale=alt.Scale(range=["#00d4ff", "#ffb020", "#8b5cf6"]),
            legend=None,
        ),
        tooltip=["Product", "Ship Date"],
    )
    .properties(height=180)
    .configure_view(stroke=None)
    .configure_axis(labelColor="#9aa4b2", gridColor="#1f2732", domainColor="#1f2732")
)

st.subheader("Launch Windows")
st.altair_chart(gantt_chart, use_container_width=True)

risk_rows = []
for product in PRODUCT_CONFIGS:
    score = confidence_score(
        yield_percent,
        throughput,
        bug_count,
        current[product]["delay_days"],
    )
    band, color = confidence_band(score)
    risk_rows.append(
        {
            "Product": product,
            "Band": "Launch Confidence",
            "Score": score,
            "Level": band,
            "Color": color,
        }
    )

risk_df = pd.DataFrame(risk_rows)
heatmap = (
    alt.Chart(risk_df)
    .mark_rect(cornerRadius=8)
    .encode(
        x=alt.X(
            "Product:N",
            title="",
            sort=list(PRODUCT_CONFIGS.keys()),
            axis=alt.Axis(labelAngle=0, labelColor="#9aa4b2"),
        ),
        y=alt.Y(
            "Band:N",
            title="",
            axis=None,
            sort=["Launch Confidence"],
            scale=alt.Scale(paddingInner=0, paddingOuter=0),
        ),
        color=alt.Color("Color:N", scale=None, legend=None),
        tooltip=["Product", "Level", "Score"],
    )
)

heatmap_text = (
    alt.Chart(risk_df)
    .mark_text(
        color="#0b0c10",
        font="Avenir Next",
        fontSize=14,
        fontWeight="bold",
    )
    .encode(
        x=alt.X("Product:N", sort=list(PRODUCT_CONFIGS.keys())),
        y=alt.Y("Band:N", sort=["Launch Confidence"]),
        text=alt.Text("Score:Q", format=".0f"),
    )
)

col_left, col_right = st.columns([1.1, 0.9], gap="large")
with col_left:
    st.subheader("Launch Confidence Score")
    layered_heatmap = (
        (heatmap + heatmap_text)
        .properties(height=alt.Step(60))
        .configure_view(stroke=None)
        .configure_axis(
            labelColor="#9aa4b2",
            domainColor="#1f2732",
        )
    )
    st.altair_chart(layered_heatmap, use_container_width=True)

with col_right:
    st.subheader("Dependency Map")
    dependency_dot = """
    digraph {
        rankdir=LR;
        node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=10 fillcolor="#11151c" color="#1f2732" fontcolor="#e6e6e6"];
        M5 [label="M5 Chip" fillcolor="#a81d1d" color="#ff4d4d" fontcolor="#ffffff"];
        Neural [label="Neural Accelerator"];
        Display [label="Liquid Glass Display"];
        Mac [label="MacBook Pro" fillcolor="#0f172a"];
        iPad [label="iPad Pro" fillcolor="#0f172a"];
        Vision [label="Vision Pro" fillcolor="#0f172a"];
        Thermal [label="Thermal System"];
        macOS [label="macOS M5 Optimization"];
        iPadOS [label="M5-optimized iPadOS"];
        Pencil [label="Pencil Pro Calibration"];
        R1 [label="R1 Sensor"];
        VisionOS [label="VisionOS Spatial UX"];

        M5 -> Mac;
        M5 -> iPad;
        M5 -> Vision;
        Neural -> Mac;
        Neural -> iPad;
        Neural -> Vision;
        Display -> Mac;
        Display -> iPad;
        Display -> Vision;
        Thermal -> Mac;
        macOS -> Mac;
        iPadOS -> iPad;
        Pencil -> iPad;
        R1 -> Vision;
        VisionOS -> Vision;
    }
    """
    st.graphviz_chart(dependency_dot)

st.subheader("Simulation Log")
st.code("\n".join(logs), language="text")
