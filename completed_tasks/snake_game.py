import pygame
import random
import sys

# 初始化pygame
pygame.init()

# 屏幕尺寸
screen_width = 600
screen_height = 400
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption('贪吃蛇游戏')

# 颜色定义
white = (255, 255, 255)
black = (0, 0, 0)
green = (0, 255, 0)
red = (255, 0, 0)

# 蛇和食物的大小
block_size = 20

# 蛇的初始位置和速度
snake_speed = 15
snake_list = []
length_of_snake = 1
score = 0

# 定义蛇的类
class Snake:
    def __init__(self):
        self.x = screen_width / 2
        self.y = screen_height / 2
        self.x_change = 0
        self.y_change = 0
        self.body = []
        self.last_direction = None

    def move(self):
        self.x += self.x_change
        self.y += self.y_change
        self.body.append([self.x, self.y])
        if len(self.body) > length_of_snake:
            del self.body[0]

    def draw(self):
        for segment in self.body:
            pygame.draw.rect(screen, green, [segment[0], segment[1], block_size, block_size])

    def check_collision(self):
        # 检查是否撞到边界
        if self.x >= screen_width or self.x < 0 or self.y >= screen_height or self.y < 0:
            return True
        # 检查是否撞到自身
        for segment in self.body[:-1]:
            if segment == [self.x, self.y]:
                return True
        return False

# 定义食物
def generate_food():
    food_x = round(random.randrange(0, screen_width - block_size) / 10.0) * 10.0
    food_y = round(random.randrange(0, screen_height - block_size) / 10.0) * 10.0
    return [food_x, food_y]

# 初始化蛇和食物
snake = Snake()
food = generate_food()

# 游戏主循环
def game_loop():
    global length_of_snake, score
    clock = pygame.time.Clock()
    game_over = False
    while not game_over:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game_over = True
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT and snake.last_direction != 'RIGHT':
                    snake.x_change = -block_size
                    snake.y_change = 0
                    snake.last_direction = 'LEFT'
                elif event.key == pygame.K_RIGHT and snake.last_direction != 'LEFT':
                    snake.x_change = block_size
                    snake.y_change = 0
                    snake.last_direction = 'RIGHT'
                elif event.key == pygame.K_UP and snake.last_direction != 'DOWN':
                    snake.y_change = -block_size
                    snake.x_change = 0
                    snake.last_direction = 'UP'
                elif event.key == pygame.K_DOWN and snake.last_direction != 'UP':
                    snake.y_change = block_size
                    snake.x_change = 0
                    snake.last_direction = 'DOWN'

        snake.move()

        # 检查碰撞
        if snake.check_collision():
            game_over = True
            print("Game Over!")
            print("Press R to restart or Q to quit")
            while game_over:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        game_over = False
                        pygame.quit()
                        sys.exit()
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_r:
                            snake = Snake()
                            food = generate_food()
                            length_of_snake = 1
                            score = 0
                            game_over = False
                            break
                        elif event.key == pygame.K_q:
                            game_over = False
                            pygame.quit()
                            sys.exit()

        # 检查是否吃到食物
        if snake.x == food[0] and snake.y == food[1]:
            food = generate_food()
            length_of_snake += 1
            score += 10

        # 绘制屏幕
        screen.fill(black)
        pygame.draw.rect(screen, red, [food[0], food[1], block_size, block_size])
        snake.draw()
        # 显示得分
        font = pygame.font.SysFont(None, 36)
        score_text = font.render(f"Score: {score}", True, white)
        screen.blit(score_text, (10, 10))
        pygame.display.update()
        clock.tick(snake_speed)

    pygame.quit()
    sys.exit()

# 启动游戏
if __name__ == '__main__':
    game_loop()