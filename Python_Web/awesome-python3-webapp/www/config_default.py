# -*-coding: utf-8 -*-
# 开始配置配置文件
'''
由于Python本身的语法简单,完全可以直接用Python源代码来实现配置,而不需要再解析一个
单独的.properties 或 .yaml等配置文件
'''

# 默认的配置文件应完全符合本地开发环境,这样,无需任何设置,就可以立即启动服务器

configs = {
    'db': {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'www-data',
        'password': 'www-data',
        'database': 'awesome'
    },
    'session': {
        'secret':'AwEsOnE'
    }
}
