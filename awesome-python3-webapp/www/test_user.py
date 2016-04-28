# -*- coding: utf-8 -*-

'''
时间:2016年04月28日22:01:32
测试数据访问数据库,编写代码操作对象
'''
import orm
from .Models import User, Blog, Comment

def test():
    yield from orm.creatr_pool(user='www-data', password='www-data', database='www-data')

    u = User(name="Test", email='test@163.com', passwd='zx123456', image='about:blank')

    yield from u.save()

for x in test():
    pass
