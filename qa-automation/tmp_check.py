import sqlite3
c = sqlite3.connect(r'E:\ai-content-marketing\apps\api\dev.db')
cur = c.execute("select id,phone,role,is_platform_admin,tenant_id,email from users where phone='13800000000'")
print('PA match:', cur.fetchall())
cur = c.execute('select count(*) from users')
print('users total:', cur.fetchone())
