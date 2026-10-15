"""
分析预计算语言嵌入的空间语义区分度

这个脚本用于检验 T5 编码器对空间词汇（如 left/right/front/back/middle）的表示
是否有足够的区分度来支持机器人任务的精确执行。
"""

import os
import sys
import torch
import numpy as np
import matplotlib.pyplot as plt
from torch.nn.functional import cosine_similarity
from collections import defaultdict

# 可选依赖
try:
    from sklearn.manifold import TSNE
    from sklearn.decomposition import PCA
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    print("警告: sklearn 未安装，将跳过 t-SNE 可视化")

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

# 配置
EMBEDDING_DIR = "outs/libero_embeddings"
OUTPUT_DIR = "outs/lang_embed_analysis"
DATASET_NAME = "libero_90"  # 可选: libero_10, libero_90, libero_spatial, libero_object, libero_goal

# 空间词汇分组
SPATIAL_KEYWORDS = {
    "left": [],
    "right": [],
    "front": [],
    "back": [],
    "middle": [],
    "top": [],
    "bottom": [],
    "under": [],
}


def load_embeddings(dataset_name):
    """加载指定数据集的所有语言嵌入"""
    embed_dir = os.path.join(EMBEDDING_DIR, dataset_name)
    embeddings = {}
    
    if not os.path.exists(embed_dir):
        print(f"错误：嵌入目录不存在: {embed_dir}")
        return embeddings
    
    for file_name in os.listdir(embed_dir):
        if file_name.endswith(".pt"):
            task_name = file_name.replace(".pt", "")
            file_path = os.path.join(embed_dir, file_name)
            embeddings[task_name] = torch.load(file_path)
    
    print(f"加载了 {len(embeddings)} 个任务的语言嵌入")
    return embeddings


def categorize_by_spatial_words(embeddings):
    """根据空间词汇对任务进行分类"""
    categorized = defaultdict(list)
    
    for task_name, embed in embeddings.items():
        task_lower = task_name.lower()
        for keyword in SPATIAL_KEYWORDS.keys():
            # 检查是否包含空间词汇（作为独立词）
            if f"_{keyword}_" in task_lower or task_lower.endswith(f"_{keyword}"):
                categorized[keyword].append((task_name, embed))
    
    return categorized


def compute_mean_embedding(embed):
    """计算嵌入的平均向量"""
    if embed.dim() == 2:
        return embed.mean(dim=0)
    return embed


def compute_similarity_matrix(embeddings):
    """计算所有任务嵌入之间的相似度矩阵"""
    task_names = list(embeddings.keys())
    n = len(task_names)
    
    # 计算平均嵌入
    mean_embeds = []
    for name in task_names:
        mean_embeds.append(compute_mean_embedding(embeddings[name]))
    
    mean_embeds = torch.stack(mean_embeds)
    
    # 计算余弦相似度矩阵
    sim_matrix = torch.zeros(n, n)
    for i in range(n):
        for j in range(n):
            sim_matrix[i, j] = cosine_similarity(
                mean_embeds[i].unsqueeze(0), 
                mean_embeds[j].unsqueeze(0)
            ).item()
    
    return sim_matrix, task_names


def analyze_spatial_pairs(embeddings):
    """分析含有对立空间词汇的任务对"""
    
    # 定义对立的空间词对
    spatial_pairs = [
        ("left", "right"),
        ("front", "back"),
        ("top", "bottom"),
        ("top", "under"),
    ]
    
    results = []
    
    for word1, word2 in spatial_pairs:
        # 找到只在空间词上不同的任务对
        tasks1 = {}
        tasks2 = {}
        
        for task_name, embed in embeddings.items():
            task_lower = task_name.lower()
            
            # 检查是否包含 word1
            if f"_{word1}_" in task_lower or f"_{word1}" in task_lower:
                # 创建规范化的键（去除空间词）
                normalized = task_lower.replace(f"_{word1}_", "_SPATIAL_").replace(f"_{word1}", "_SPATIAL")
                tasks1[normalized] = (task_name, embed)
            
            # 检查是否包含 word2
            if f"_{word2}_" in task_lower or f"_{word2}" in task_lower:
                normalized = task_lower.replace(f"_{word2}_", "_SPATIAL_").replace(f"_{word2}", "_SPATIAL")
                tasks2[normalized] = (task_name, embed)
        
        # 找到匹配的任务对
        for key in tasks1:
            if key in tasks2:
                name1, embed1 = tasks1[key]
                name2, embed2 = tasks2[key]
                
                mean1 = compute_mean_embedding(embed1)
                mean2 = compute_mean_embedding(embed2)
                
                sim = cosine_similarity(mean1.unsqueeze(0), mean2.unsqueeze(0)).item()
                
                results.append({
                    "pair": (word1, word2),
                    "task1": name1,
                    "task2": name2,
                    "similarity": sim,
                    "difference": 1 - sim
                })
    
    return results


def find_same_scene_tasks(embeddings):
    """找出同一场景下不同空间位置的任务"""
    scene_groups = defaultdict(list)
    
    for task_name, embed in embeddings.items():
        # 提取场景名
        parts = task_name.split("_")
        if len(parts) >= 2 and "SCENE" in task_name:
            # 找到 SCENE 的位置
            for i, part in enumerate(parts):
                if "SCENE" in part:
                    scene_name = "_".join(parts[:i+1])
                    scene_groups[scene_name].append((task_name, embed))
                    break
    
    return scene_groups


def visualize_embeddings_tsne(embeddings, categorized, output_path):
    """使用 t-SNE 可视化嵌入空间"""
    
    if not HAS_SKLEARN:
        print("跳过 t-SNE 可视化（sklearn 未安装）")
        return
    
    # 准备数据
    all_embeds = []
    labels = []
    colors = []
    
    color_map = {
        "left": "red",
        "right": "blue", 
        "front": "green",
        "back": "orange",
        "middle": "purple",
        "top": "cyan",
        "bottom": "magenta",
        "under": "brown",
        "other": "gray"
    }
    
    for task_name, embed in embeddings.items():
        mean_embed = compute_mean_embedding(embed)
        all_embeds.append(mean_embed.numpy())
        
        # 确定标签
        task_lower = task_name.lower()
        label = "other"
        for keyword in SPATIAL_KEYWORDS.keys():
            if f"_{keyword}_" in task_lower or task_lower.endswith(f"_{keyword}"):
                label = keyword
                break
        
        labels.append(label)
        colors.append(color_map.get(label, "gray"))
    
    all_embeds = np.stack(all_embeds)
    
    # t-SNE 降维
    print("正在进行 t-SNE 降维...")
    tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(all_embeds)-1))
    embeds_2d = tsne.fit_transform(all_embeds)
    
    # 绘图
    plt.figure(figsize=(14, 10))
    
    # 按类别绘制
    for label in set(labels):
        mask = [l == label for l in labels]
        indices = [i for i, m in enumerate(mask) if m]
        
        plt.scatter(
            embeds_2d[indices, 0],
            embeds_2d[indices, 1],
            c=color_map.get(label, "gray"),
            label=f"{label} ({len(indices)})",
            alpha=0.7,
            s=100
        )
    
    plt.title(f"T5 Language Embeddings - Spatial Words Visualization\n({DATASET_NAME})", fontsize=14)
    plt.xlabel("t-SNE Dimension 1")
    plt.ylabel("t-SNE Dimension 2")
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"t-SNE 可视化已保存到: {output_path}")


def visualize_similarity_heatmap(spatial_results, output_path):
    """可视化空间词对的相似度"""
    
    if not spatial_results:
        print("没有找到空间词对，跳过热力图")
        return
    
    # 按词对分组
    pair_similarities = defaultdict(list)
    for result in spatial_results:
        pair_key = f"{result['pair'][0]} vs {result['pair'][1]}"
        pair_similarities[pair_key].append(result['similarity'])
    
    # 创建柱状图
    plt.figure(figsize=(12, 6))
    
    pairs = list(pair_similarities.keys())
    means = [np.mean(sims) for sims in pair_similarities.values()]
    stds = [np.std(sims) for sims in pair_similarities.values()]
    counts = [len(sims) for sims in pair_similarities.values()]
    
    x = np.arange(len(pairs))
    bars = plt.bar(x, means, yerr=stds, capsize=5, color='steelblue', alpha=0.8)
    
    # 添加数量标注
    for i, (bar, count) in enumerate(zip(bars, counts)):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + stds[i] + 0.01,
                f'n={count}', ha='center', va='bottom', fontsize=10)
    
    plt.xticks(x, pairs, fontsize=12)
    plt.ylabel("Cosine Similarity", fontsize=12)
    plt.title(f"Similarity Between Opposite Spatial Word Pairs\n({DATASET_NAME})", fontsize=14)
    plt.ylim(0, 1.1)
    
    # 添加参考线
    plt.axhline(y=0.95, color='red', linestyle='--', alpha=0.5, label='High Similarity (0.95)')
    plt.axhline(y=0.90, color='orange', linestyle='--', alpha=0.5, label='Moderate (0.90)')
    plt.legend()
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"相似度柱状图已保存到: {output_path}")


def analyze_scene_tasks(scene_groups, output_path):
    """分析同一场景内不同任务的嵌入相似度"""
    
    results = []
    
    for scene_name, tasks in scene_groups.items():
        if len(tasks) < 2:
            continue
        
        # 计算场景内所有任务对的相似度
        for i in range(len(tasks)):
            for j in range(i + 1, len(tasks)):
                name1, embed1 = tasks[i]
                name2, embed2 = tasks[j]
                
                mean1 = compute_mean_embedding(embed1)
                mean2 = compute_mean_embedding(embed2)
                
                sim = cosine_similarity(mean1.unsqueeze(0), mean2.unsqueeze(0)).item()
                
                results.append({
                    "scene": scene_name,
                    "task1": name1,
                    "task2": name2,
                    "similarity": sim
                })
    
    # 按场景统计
    scene_stats = defaultdict(list)
    for r in results:
        scene_stats[r["scene"]].append(r["similarity"])
    
    # 绘制箱线图
    if scene_stats:
        plt.figure(figsize=(14, 6))
        
        scenes = list(scene_stats.keys())
        data = [scene_stats[s] for s in scenes]
        
        # 简化场景名称用于显示
        short_names = [s.replace("KITCHEN_", "K_").replace("LIVING_ROOM_", "LR_").replace("STUDY_", "S_") 
                      for s in scenes]
        
        bp = plt.boxplot(data, labels=short_names, patch_artist=True)
        
        for patch in bp['boxes']:
            patch.set_facecolor('lightblue')
        
        plt.xticks(rotation=45, ha='right')
        plt.ylabel("Cosine Similarity", fontsize=12)
        plt.title(f"Intra-Scene Task Embedding Similarity\n({DATASET_NAME})", fontsize=14)
        plt.axhline(y=0.95, color='red', linestyle='--', alpha=0.5, label='High Similarity (0.95)')
        plt.legend()
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"场景内相似度分析已保存到: {output_path}")
    
    return results


def generate_report(embeddings, spatial_results, scene_results, output_path):
    """生成文本分析报告"""
    
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append(f"T5 语言嵌入空间语义区分度分析报告")
    report_lines.append(f"数据集: {DATASET_NAME}")
    report_lines.append(f"任务总数: {len(embeddings)}")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # 1. 空间词对分析
    report_lines.append("## 1. 对立空间词对相似度分析")
    report_lines.append("-" * 40)
    
    if spatial_results:
        # 按词对分组
        pair_results = defaultdict(list)
        for r in spatial_results:
            pair_results[r["pair"]].append(r)
        
        for pair, results in pair_results.items():
            sims = [r["similarity"] for r in results]
            report_lines.append(f"\n### {pair[0]} vs {pair[1]} ({len(results)} 对)")
            report_lines.append(f"  平均相似度: {np.mean(sims):.4f}")
            report_lines.append(f"  最小相似度: {np.min(sims):.4f}")
            report_lines.append(f"  最大相似度: {np.max(sims):.4f}")
            report_lines.append(f"  标准差: {np.std(sims):.4f}")
            
            report_lines.append(f"\n  详细任务对:")
            for r in sorted(results, key=lambda x: x["similarity"]):
                report_lines.append(f"    {r['similarity']:.4f}: ")
                report_lines.append(f"      - {r['task1']}")
                report_lines.append(f"      - {r['task2']}")
    else:
        report_lines.append("  未找到对立空间词对")
    
    report_lines.append("")
    
    # 2. 场景内分析
    report_lines.append("\n## 2. 同一场景内任务相似度统计")
    report_lines.append("-" * 40)
    
    if scene_results:
        scene_stats = defaultdict(list)
        for r in scene_results:
            scene_stats[r["scene"]].append(r["similarity"])
        
        for scene, sims in sorted(scene_stats.items()):
            report_lines.append(f"\n### {scene}")
            report_lines.append(f"  任务对数: {len(sims)}")
            report_lines.append(f"  平均相似度: {np.mean(sims):.4f}")
            report_lines.append(f"  范围: [{np.min(sims):.4f}, {np.max(sims):.4f}]")
    
    report_lines.append("")
    
    # 3. 诊断结论
    report_lines.append("\n## 3. 诊断结论")
    report_lines.append("-" * 40)
    
    if spatial_results:
        all_spatial_sims = [r["similarity"] for r in spatial_results]
        avg_sim = np.mean(all_spatial_sims)
        
        if avg_sim > 0.95:
            report_lines.append(f"\n⚠️ 警告: 对立空间词的平均相似度为 {avg_sim:.4f}")
            report_lines.append("  这表明 T5 嵌入无法有效区分不同的空间位置。")
            report_lines.append("  建议:")
            report_lines.append("    1. 添加可训练的语言适配层")
            report_lines.append("    2. 使用空间词特定的嵌入增强")
            report_lines.append("    3. 考虑不使用预计算嵌入，让 T5 参与微调")
        elif avg_sim > 0.90:
            report_lines.append(f"\n⚠️ 注意: 对立空间词的平均相似度为 {avg_sim:.4f}")
            report_lines.append("  空间词有一定区分度，但可能仍需改进。")
        else:
            report_lines.append(f"\n✓ 良好: 对立空间词的平均相似度为 {avg_sim:.4f}")
            report_lines.append("  T5 嵌入对空间词有较好的区分能力。")
    
    report_lines.append("")
    report_lines.append("=" * 80)
    
    # 写入文件
    report_text = "\n".join(report_lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    
    print(f"\n分析报告已保存到: {output_path}")
    print("\n" + report_text)


def main():
    """主函数"""
    
    # 创建输出目录
    output_dir = os.path.join(OUTPUT_DIR, DATASET_NAME)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"开始分析 {DATASET_NAME} 的语言嵌入...")
    print("=" * 60)
    
    # 1. 加载嵌入
    embeddings = load_embeddings(DATASET_NAME)
    if not embeddings:
        print("无法加载嵌入，退出")
        return
    
    # 2. 按空间词分类
    categorized = categorize_by_spatial_words(embeddings)
    print(f"\n空间词汇分布:")
    for keyword, tasks in categorized.items():
        if tasks:
            print(f"  {keyword}: {len(tasks)} 个任务")
    
    # 3. 分析空间词对
    print("\n分析对立空间词对...")
    spatial_results = analyze_spatial_pairs(embeddings)
    print(f"找到 {len(spatial_results)} 对空间对立任务")
    
    # 4. 分析场景内任务
    print("\n分析同场景任务...")
    scene_groups = find_same_scene_tasks(embeddings)
    scene_results = analyze_scene_tasks(
        scene_groups, 
        os.path.join(output_dir, "scene_similarity_boxplot.png")
    )
    
    # 5. 可视化
    print("\n生成可视化...")
    visualize_embeddings_tsne(
        embeddings, 
        categorized,
        os.path.join(output_dir, "tsne_visualization.png")
    )
    
    visualize_similarity_heatmap(
        spatial_results,
        os.path.join(output_dir, "spatial_pair_similarity.png")
    )
    
    # 6. 生成报告
    generate_report(
        embeddings,
        spatial_results,
        scene_results,
        os.path.join(output_dir, "analysis_report.txt")
    )
    
    print("\n分析完成!")
    print(f"所有结果已保存到: {output_dir}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="分析语言嵌入的空间语义区分度")
    parser.add_argument("--dataset", type=str, default="libero_90",
                        choices=["libero_10", "libero_90", "libero_spatial", "libero_object", "libero_goal"],
                        help="要分析的数据集名称")
    parser.add_argument("--embed-dir", type=str, default="outs/libero_embeddings",
                        help="语言嵌入目录")
    parser.add_argument("--output-dir", type=str, default="outs/lang_embed_analysis",
                        help="输出目录")
    
    args = parser.parse_args()
    
    DATASET_NAME = args.dataset
    EMBEDDING_DIR = args.embed_dir
    OUTPUT_DIR = args.output_dir
    
    main()

