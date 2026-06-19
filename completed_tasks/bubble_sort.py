def bubble_sort(arr):
    n = len(arr)
    # 遍历所有数组元素
    for i in range(n):
        # 最后i个元素已到位，无需再比较
        for j in range(0, n-i-1):
            # 如果当前元素比下一个元素大，交换它们
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]

# 示例用法
if __name__ == "__main__":
    sample_list = [64, 34, 25, 12, 22, 11, 90]
    print("原始列表:", sample_list)
    bubble_sort(sample_list)
    print("排序后的列表:", sample_list)