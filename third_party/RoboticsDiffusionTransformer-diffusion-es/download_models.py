import os
import subprocess
from huggingface_hub import snapshot_download

# 设置本地模型保存路径
BASE_DIR = os.path.abspath(".")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "models_download")  # 可改成其他路径
T5_PATH = os.path.join(DOWNLOAD_DIR, "t5-v1_1-xxl")
SIGLIP_PATH = os.path.join(DOWNLOAD_DIR, "siglip-so400m-patch14-384")
RDT_PATH = os.path.join(DOWNLOAD_DIR, "rdt-1b")
LINK_DIR = os.path.join(BASE_DIR, "google")

print("当前工作目录:", BASE_DIR)
print("模型下载目录:", DOWNLOAD_DIR)
print("软链接目录:", LINK_DIR)

# 下载模型函数
def download_model(repo_id: str, local_dir: str):
    print(f"�� 正在下载模型：{repo_id}")
    snapshot_download(
        repo_id=repo_id,
        local_dir=local_dir,
        local_dir_use_symlinks=False,
        resume_download=True
    )
    print(f"✅ 模型下载完成：{repo_id}\n")

# 创建软连接函数
def create_symlink(source: str, link_name: str):
    if os.path.islink(link_name) or os.path.exists(link_name):
        print(f"�� 已存在，跳过软链接创建: {link_name}")
    else:
        os.symlink(source, link_name)
        print(f"✅ 创建软链接: {link_name} → {source}")

def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(LINK_DIR, exist_ok=True)

    # # 下载两个模型
    # download_model("google/t5-v1_1-xxl", T5_PATH)
    # download_model("google/siglip-so400m-patch14-384", SIGLIP_PATH)
    # download_model("robotics-diffusion-transformer/rdt-1b", RDT_PATH)

    # 创建软链接到 google/ 下
    create_symlink(T5_PATH, os.path.join(LINK_DIR, "t5-v1_1-xxl"))
    create_symlink(SIGLIP_PATH, os.path.join(LINK_DIR, "siglip-so400m-patch14-384"))
    create_symlink(RDT_PATH, os.path.join(LINK_DIR, "rdt-1b"))

    print("\n✅ 所有操作完成！模型已下载并链接至 ./google/ 目录")

if __name__ == "__main__":
    main()