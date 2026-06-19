import pygame
import sys
import random

# 初始化pygame
pygame.init()

# 设置窗口
window_size = [800, 600]
window = pygame.display.set_mode(window_size)
pygame.display.set_caption("Game Window")

# 颜色定义
black = (0, 0, 0)
white = (255, 255, 255)
green = (0, 255, 0)
red = (255, 0, 0)

# 蛇的初始位置和速度
snake_pos = [100, 50]
snake_speed = [10, 0]

# 蛇的身体
snake_body = [[100, 50], [90, 50], [80, 50]]

# 食物的位置
food_pos = [random.randint(0, window_size[0] // 10 - 1) * 10, random.randint(0, window_size[1] // 10 - 1) * 10]
food_spawn = True

# 游戏循环
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    # 控制蛇的移动
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:
        snake_speed = [-10, 0]
    elif keys[pygame.K_RIGHT]:
        snake_speed = [10, 0]
    elif keys[pygame.K_UP]:
        snake_speed = [0, -10]
    elif keys[pygame.K_DOWN]:
        snake_speed = [0, 10]

    # 移动蛇头
    snake_pos[0] += snake_speed[0]
    snake_pos[1] += snake_speed[1]

    # 将新的头部添加到身体列表中
    snake_body.insert(0, list(snake_pos))

    # 检查是否吃到食物
    if snake_pos == food_pos:
        food_spawn = False
    else:
        snake_body.pop()

    # 如果没有吃到食物，移除尾部
    if not food_spawn:
        food_pos = [random.randint(0, window_size[0] // 10 - 1) * 10, random.randint(0, window_size[1] // 10 - 1) * 10]
        food_spawn = True

    # 绘制背景
    window.fill(black)

    # 绘制蛇
    for pos in snake_body:
        pygame.draw.rect(window, green, pygame.Rect(pos[0], pos[1], 10, 10))

    # 绘制食物
    pygame.draw.rect(window, red, pygame.Rect(food_pos[0], food_pos[1], 10, 10))

    # 更新屏幕
    pygame.display.update()

    # 控制游戏速度
    pygame.time.Clock().tick(20)