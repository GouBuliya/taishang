from PIL import Image
import os

def merge_images_vertically(image_paths, output_path, quality=1): # 建议将默认值设为更常用的85
    """
    垂直堆叠多张图片并保存，支持画质压缩。

    Args:
        image_paths (list): 包含要合并的图片文件路径的列表。
        output_path (str): 合并后图片的保存路径。
        quality (int, optional): 图片保存的画质，范围通常是 1-95。
                                 对于JPEG格式有效。默认值为 85。
    """
    if not image_paths:
        print("错误：没有提供图片路径。")
        return

    # !!! 移除这一行，让 quality 参数通过函数调用传入 !!!
    # quality=35

    images = []
    for img_path in image_paths:
        try:
            images.append(Image.open(img_path))
        except FileNotFoundError:
            print(f"错误：文件未找到 - {img_path}")
            return
        except Exception as e:
            print(f"错误：打开图片 {img_path} 时发生异常 - {e}")
            return


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

    # 保存合并后的图片，并应用画质压缩
    # quality 参数主要对 JPEG 格式有效。对于 PNG 等无损格式，此参数可能无效或行为不同。
    # 因此，确保 output_path 的文件扩展名是 .jpg 或 .jpeg
    try:
        # 显式指定 format='JPEG'，确保即使文件名扩展名不符，也尝试保存为 JPEG
        merged_image.save(output_path, quality=quality, format='JPEG')
        print(f"图片已成功合并并保存到: {output_path} (画质: {quality})")
    except Exception as e:
        print(f"保存合并图片到 {output_path} 失败: {e}")

# filepath: /home/li-xufeng/codespace/taishang/merge_screenshots.py
# The provided code was already complete up to the point of saving.
# The completion adds the save call and a confirmation message.