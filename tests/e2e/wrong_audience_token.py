"""为 Playwright 第 5 步生成受众不符的令牌。

user1 登录后交换到 AI 网关受众（不含 contexture-bff）。
"""

from support.cluster import exchange, user_token

if __name__ == "__main__":
    print(exchange(user_token("user1", "user1"), audience="contexture-ai-gateway"))
