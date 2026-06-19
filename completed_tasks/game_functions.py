def game_over():
    print("Game Over!")
    # 可以在这里添加重新开始的逻辑，例如重置游戏状态

# 示例：重新开始游戏
def restart_game():
    global score, snake_body, food_pos
    score = 0
    snake_body = [[100, 50]]
    food_pos = generate_food(snake_body)

# 在游戏循环中调用 game_over() 来结束游戏
# 例如，在蛇头碰到边界或自身时调用 game_over()

# 在 game_over() 中可以调用 restart_game() 来重新开始游戏