from PIL import Image
import os

def merge_images_vertically(image_paths, output_path):
    """
    垂直堆叠多张图片并保存。

    Args:
        image_paths (list): 包含要合并的图片文件路径的列表。
        output_path (str): 合并后图片的保存路径。
    """
    if not image_paths:
        print("错误：没有提供图片路径。")
        return

    images = [Image.open(img_path) for img_path in image_paths]

    # 找到最宽的图片宽度
    max_width = max(img.width for img in images)

    # 计算合并后的总高度
    total_height = sum(img.height for img in images)

    # 创建一个新的空白图片，宽度为最宽图片的宽度，高度为总高度
    merged_image = Image.new('RGB', (max_width, total_height))

    # 将每张图片粘贴到新图片上
    y_offset = 0
    for img in images:
        merged_image.paste(img, (0, y_offset))
        y_offset += img.height

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 保存合并后的图片
    merged_image.save(output_path)
    print(f"图片已成功合并并保存到: {output_path}")

# filepath: /home/li-xufeng/codespace/taishang/merge_screenshots.py
# The provided code was already complete up to the point of saving.
# The completion adds the save call and a confirmation message.