"""
专门分析 libero_spatial 数据集的语言嵌入相似度

这个数据集的特点是：所有任务都是 "pick up the black bowl [位置描述] and place it on the plate"
区别仅在于位置描述部分，如：
- on the stove
- next to the ramekin
- in the top drawer
- between the plate and the ramekin
等等

我们需要检验 T5 是否能有效区分这些不同的位置描述。
"""

import os
import torch
import numpy as np
import matplotlib.pyplot as plt
from torch.nn.functional import cosine_similarity
from collections import defaultdict

EMBEDDING_DIR = "outs/libero_embeddings/libero_spatial"
OUTPUT_DIR = "outs/lang_embed_analysis/libero_spatial"


def extract_location_from_task(task_name):
    """从任务名称中提取位置描述"""
    # 格式: pick_up_the_black_bowl_[LOCATION]_and_place_it_on_the_plate
    prefix = "pick_up_the_black_bowl_"
    suffix = "_and_place_it_on_the_plate"
    
    if task_name.startswith(prefix) and task_name.endswith(suffix):
        location = task_name[len(prefix):-len(suffix)]
        return location.replace("_", " ")
    return task_name


def load_embeddings():
    """加载所有语言嵌入"""
    embeddings = {}
    
    for file_name in os.listdir(EMBEDDING_DIR):
        if file_name.endswith(".pt"):
            task_name = file_name.replace(".pt", "")
            file_path = os.path.join(EMBEDDING_DIR, file_name)
            embeddings[task_name] = torch.load(file_path)
    
    return embeddings


def compute_mean_embedding(embed):
    """计算嵌入的平均向量"""
    if embed.dim() == 2:
        return embed.mean(dim=0)
    return embed


def compute_all_pairs_similarity(embeddings):
    """计算所有任务对的相似度"""
    task_names = list(embeddings.keys())
    n = len(task_names)
    
    results = []
    similarity_matrix = np.zeros((n, n))
    
    for i in range(n):
        embed_i = compute_mean_embedding(embeddings[task_names[i]])
        for j in range(n):
            embed_j = compute_mean_embedding(embeddings[task_names[j]])
            sim = cosine_similarity(embed_i.unsqueeze(0), embed_j.unsqueeze(0)).item()
            similarity_matrix[i, j] = sim
            
            if i < j:
                results.append({
                    "task1": task_names[i],
                    "task2": task_names[j],
                    "location1": extract_location_from_task(task_names[i]),
                    "location2": extract_location_from_task(task_names[j]),
                    "similarity": sim
                })
    
    return results, similarity_matrix, task_names


def visualize_similarity_matrix(similarity_matrix, task_names, output_path):
    """可视化相似度矩阵"""
    
    # 提取位置描述作为标签
    locations = [extract_location_from_task(name) for name in task_names]
    
    # 缩短标签
    short_labels = []
    for loc in locations:
        if len(loc) > 20:
            short_labels.append(loc[:17] + "...")
        else:
            short_labels.append(loc)
    
    plt.figure(figsize=(12, 10))
    
    # 绘制热力图
    im = plt.imshow(similarity_matrix, cmap='RdYlGn_r', vmin=0.8, vmax=1.0)
    
    # 添加颜色条
    cbar = plt.colorbar(im)
    cbar.set_label('Cosine Similarity', fontsize=12)
    
    # 设置轴标签
    plt.xticks(range(len(short_labels)), short_labels, rotation=45, ha='right', fontsize=9)
    plt.yticks(range(len(short_labels)), short_labels, fontsize=9)
    
    # 添加数值标注
    for i in range(len(task_names)):
        for j in range(len(task_names)):
            text_color = 'white' if similarity_matrix[i, j] > 0.95 else 'black'
            plt.text(j, i, f'{similarity_matrix[i, j]:.2f}',
                    ha='center', va='center', fontsize=7, color=text_color)
    
    plt.title('libero_spatial: Task Embedding Similarity Matrix\n(All tasks share same action, differ only in location)', fontsize=12)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"相似度矩阵已保存到: {output_path}")


def visualize_similarity_distribution(results, output_path):
    """可视化相似度分布"""
    
    similarities = [r["similarity"] for r in results]
    
    plt.figure(figsize=(10, 6))
    
    # 直方图
    plt.hist(similarities, bins=20, edgecolor='black', alpha=0.7, color='steelblue')
    
    # 添加统计线
    mean_sim = np.mean(similarities)
    min_sim = np.min(similarities)
    max_sim = np.max(similarities)
    
    plt.axvline(mean_sim, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_sim:.3f}')
    plt.axvline(min_sim, color='green', linestyle='--', linewidth=2, label=f'Min: {min_sim:.3f}')
    plt.axvline(max_sim, color='orange', linestyle='--', linewidth=2, label=f'Max: {max_sim:.3f}')
    
    # 危险区域
    plt.axvspan(0.95, 1.0, alpha=0.3, color='red', label='High Similarity Zone (>0.95)')
    
    plt.xlabel('Cosine Similarity', fontsize=12)
    plt.ylabel('Number of Task Pairs', fontsize=12)
    plt.title(f'libero_spatial: Pairwise Task Similarity Distribution\n(Total {len(similarities)} pairs)', fontsize=12)
    plt.legend()
    plt.xlim(0.7, 1.0)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    print(f"相似度分布图已保存到: {output_path}")


def generate_report(embeddings, results, output_path):
    """生成分析报告"""
    
    lines = []
    lines.append("=" * 80)
    lines.append("libero_spatial 数据集语言嵌入分析报告")
    lines.append("=" * 80)
    lines.append("")
    
    # 数据集特点
    lines.append("## 数据集特点")
    lines.append("-" * 40)
    lines.append("所有任务都是: pick up the black bowl [位置] and place it on the plate")
    lines.append("唯一区别: 碗的位置描述不同")
    lines.append("")
    
    # 任务列表
    lines.append("## 任务位置描述")
    lines.append("-" * 40)
    for task_name in sorted(embeddings.keys()):
        location = extract_location_from_task(task_name)
        lines.append(f"  - {location}")
    lines.append("")
    
    # 统计信息
    similarities = [r["similarity"] for r in results]
    lines.append("## 相似度统计")
    lines.append("-" * 40)
    lines.append(f"任务对总数: {len(results)}")
    lines.append(f"平均相似度: {np.mean(similarities):.4f}")
    lines.append(f"最小相似度: {np.min(similarities):.4f}")
    lines.append(f"最大相似度: {np.max(similarities):.4f}")
    lines.append(f"标准差: {np.std(similarities):.4f}")
    lines.append("")
    
    # 高相似度任务对（问题区域）
    lines.append("## ⚠️ 高相似度任务对 (>0.95)")
    lines.append("-" * 40)
    high_sim_pairs = [r for r in results if r["similarity"] > 0.95]
    high_sim_pairs.sort(key=lambda x: -x["similarity"])
    
    if high_sim_pairs:
        for r in high_sim_pairs:
            lines.append(f"\n相似度: {r['similarity']:.4f}")
            lines.append(f"  位置1: {r['location1']}")
            lines.append(f"  位置2: {r['location2']}")
    else:
        lines.append("  无")
    lines.append("")
    
    # 低相似度任务对（好区分的）
    lines.append("## ✓ 低相似度任务对 (<0.85)")
    lines.append("-" * 40)
    low_sim_pairs = [r for r in results if r["similarity"] < 0.85]
    low_sim_pairs.sort(key=lambda x: x["similarity"])
    
    if low_sim_pairs:
        for r in low_sim_pairs[:10]:  # 只显示前10个
            lines.append(f"\n相似度: {r['similarity']:.4f}")
            lines.append(f"  位置1: {r['location1']}")
            lines.append(f"  位置2: {r['location2']}")
    else:
        lines.append("  无")
    lines.append("")
    
    # 诊断结论
    lines.append("## 诊断结论")
    lines.append("-" * 40)
    
    avg_sim = np.mean(similarities)
    high_sim_count = len([s for s in similarities if s > 0.95])
    
    if avg_sim > 0.92:
        lines.append(f"\n🔴 严重问题: 平均相似度 {avg_sim:.4f}")
        lines.append("   所有任务的语言嵌入高度相似，模型几乎无法从语言条件中区分不同位置。")
        lines.append("   这意味着模型必须完全依赖图像来判断碗的位置。")
    elif avg_sim > 0.88:
        lines.append(f"\n🟠 中等问题: 平均相似度 {avg_sim:.4f}")
        lines.append("   任务嵌入有一定区分度，但仍可能不足。")
    else:
        lines.append(f"\n🟢 良好: 平均相似度 {avg_sim:.4f}")
        lines.append("   任务嵌入有较好的区分度。")
    
    if high_sim_count > 0:
        lines.append(f"\n⚠️ 有 {high_sim_count} 对任务相似度 > 0.95")
        lines.append("   这些任务对模型来说几乎无法区分。")
    
    lines.append("")
    lines.append("=" * 80)
    
    # 与 libero_90 对比
    lines.append("\n## 与 libero_90 对比")
    lines.append("-" * 40)
    lines.append("libero_90 空间词对平均相似度: ~0.91")
    lines.append(f"libero_spatial 平均相似度: {avg_sim:.4f}")
    
    if avg_sim > 0.91:
        lines.append("\n结论: libero_spatial 的问题比 libero_90 更严重！")
        lines.append("原因: 所有任务只有位置描述不同，其他部分完全相同，")
        lines.append("      导致 T5 嵌入被共同部分主导，位置差异信息被稀释。")
    else:
        lines.append("\n结论: libero_spatial 的区分度与 libero_90 相当。")
    
    lines.append("")
    
    # 写入文件
    report_text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    
    print(f"\n分析报告已保存到: {output_path}")
    print("\n" + report_text)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("libero_spatial 语言嵌入深度分析")
    print("=" * 60)
    
    # 加载嵌入
    embeddings = load_embeddings()
    print(f"\n加载了 {len(embeddings)} 个任务的嵌入")
    
    # 计算相似度
    print("\n计算所有任务对的相似度...")
    results, sim_matrix, task_names = compute_all_pairs_similarity(embeddings)
    
    # 可视化
    visualize_similarity_matrix(
        sim_matrix, task_names,
        os.path.join(OUTPUT_DIR, "similarity_matrix.png")
    )
    
    visualize_similarity_distribution(
        results,
        os.path.join(OUTPUT_DIR, "similarity_distribution.png")
    )
    
    # 生成报告
    generate_report(
        embeddings, results,
        os.path.join(OUTPUT_DIR, "detailed_analysis_report.txt")
    )


if __name__ == "__main__":
    main()








