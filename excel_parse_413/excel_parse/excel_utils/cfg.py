import logging

version = "v1.1.5"

# 本项目不再使用 server_config.json / 在线激活模型配置。
# 统一使用本地 cur_model 配置。
cur_model = {
    "model_name": "gpt-5.2",
    "base_url": "http://192.168.145.16/v1/",
    "api_key": "sk-LA4KngJCQfVfsSLD7xjkfmxdpvSKUljIL7gEsb2OVKqaaihh",
    "temperature": 0,
    "max_tokens": None,
    # "top_p": None,
}


# jwt 认证使用
SECRET_KEY = "django-insecure--7vx%kl$_z(dz(3&8g@f$ua=6gb!xcr(tl)du+(mwryr$66n-c"
ALGORITHM = "HS256"
