import json
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
from datetime import datetime

# ------------------------------
# 1. 读取 jsonl 文件
# ------------------------------
records = []
with open("lfg_events.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            records.append(json.loads(line))

df = pd.DataFrame(records)

# 辅助函数：从嵌套 extra 中安全提取字段
def get_extra_field(row, field, default=None):
    extra = row.get("extra")
    if isinstance(extra, dict):
        return extra.get(field, default)
    return default

# 提取房主名字（create 事件专用）
def get_host_name(row):
    if row.get("event") != "create":
        return None
    # 优先直接从行内取，否则从 extra 里取
    if "host_name" in row:
        return row["host_name"]
    return get_extra_field(row, "host_name")

df["host_name_clean"] = df.apply(get_host_name, axis=1)

# 提取游戏模式（create 事件）
def get_mode(row):
    if row.get("event") != "create":
        return None
    if "mode" in row:
        return row["mode"]
    return get_extra_field(row, "mode")

df["mode_clean"] = df.apply(get_mode, axis=1)

# ------------------------------
# 2. 基础统计
# ------------------------------
creates = df[df["event"] == "create"]
total_lobbies = len(creates)
print(f"📊 总开房数：{total_lobbies}")

# 模式分布
mode_dist = creates["mode_clean"].value_counts()
print("\n🎮 模式分布：")
for mode, count in mode_dist.items():
    print(f"  {mode}: {count} 次")

# 完成率：有 finish 事件的房间 / 总开房数
finish_ids = set(df[df["event"] == "finish"]["session_id"].dropna())
if total_lobbies > 0:
    completion_rate = len(finish_ids) / total_lobbies * 100
else:
    completion_rate = 0
print(f"\n✅ 完成率：{completion_rate:.1f}% （{len(finish_ids)}/{total_lobbies}）")

# 平均时长（仅对 finish 事件且 duration_seconds 存在）
finish_df = df[(df["event"] == "finish") & (df["duration_seconds"].notna())]
if not finish_df.empty:
    avg_duration = finish_df["duration_seconds"].mean()
    print(f"⏱️ 平均游戏时长：{avg_duration:.1f} 秒 ({avg_duration/60:.1f} 分钟)")
else:
    print("⏱️ 没有有效的完成时长记录")

# 按小时统计活动（所有事件）
df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour
hourly_activity = df.groupby("hour").size()
print("\n📈 按小时活动分布（总事件数）：")
for hour in range(24):
    count = hourly_activity.get(hour, 0)
    if count > 0:
        print(f"  {hour:02d}:00  {count} 次")

# ------------------------------
# 3. 生成柱状图并保存
# ------------------------------
plt.rcParams["font.sans-serif"] = ["SimHei"]  # 用于显示中文
plt.rcParams["axes.unicode_minus"] = False

fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# 图1：模式分布
ax1 = axes[0, 0]
mode_dist.plot(kind="bar", ax=ax1, color="skyblue")
ax1.set_title("开房模式分布")
ax1.set_xlabel("模式")
ax1.set_ylabel("次数")
ax1.tick_params(axis="x", rotation=45)

# 图2：完成率饼图
ax2 = axes[0, 1]
labels = ["已完成", "未完成"]
sizes = [len(finish_ids), total_lobbies - len(finish_ids)]
ax2.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90, colors=["lightgreen", "lightcoral"])
ax2.set_title("完成率")

# 图3：按小时活动柱状图
ax3 = axes[1, 0]
hours = list(range(24))
counts = [hourly_activity.get(h, 0) for h in hours]
ax3.bar(hours, counts, color="orange")
ax3.set_title("按小时活动分布（所有事件）")
ax3.set_xlabel("小时 (0-23)")
ax3.set_ylabel("事件次数")
ax3.set_xticks(range(0, 24, 2))

# 图4：平均时长（如果有数据）
ax4 = axes[1, 1]
if not finish_df.empty:
    # 可选：画出每次完成的时长散点图
    durations = finish_df["duration_seconds"].values / 60  # 转为分钟
    ax4.hist(durations, bins=10, color="purple", alpha=0.7)
    ax4.set_title("游戏时长分布（分钟）")
    ax4.set_xlabel("时长（分钟）")
    ax4.set_ylabel("房间数量")
else:
    ax4.text(0.5, 0.5, "暂无完成时长数据", ha="center", va="center", transform=ax4.transAxes)
    ax4.set_title("游戏时长分布")

plt.tight_layout()
plt.savefig("lfg_activity.png", dpi=150)
print("\n📁 图表已保存为 lfg_activity.png")
plt.show()
