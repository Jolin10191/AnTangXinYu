# 数据库备份

生产库里存着用户的对话、健康档案和手环观测，丢了没有第二份。备份是每天 04:30 由
systemd timer 触发的一次 `pg_dump`，**加密之后才落盘**。

## 为什么加密

`pg_dump` 的产物是明文，里面有用户名、对话内容和心率血氧记录。服务器上的备份目录
如果被读走（比如误配了静态目录、或者快照被分享），明文就等于把用户数据全交出去。
所以流水线是：

```
docker exec pg_dump --format=custom | gzip -9 | gpg --symmetric --cipher-algo AES256
```

明文不出内存，落盘的只有 `.dump.gz.gpg`。

## 口令

口令单独存在 `/home/ubuntu/.antang-backup.pass`（权限 600），**与备份文件分开**：

- 备份文件可能被拷到别处，拷走的人没有口令打不开；
- 口令丢了，备份也就打不开了。请把口令另存一份到密码管理器，不要只留在服务器上。

换口令不会自动重加密旧备份：旧备份仍然需要旧口令。要换之前先把旧备份用新口令重新
加密一遍，或用旧口令恢复后再用新口令备份一次。

## 定时执行

```bash
sudo cp infra/systemd/antang-backup.service /etc/systemd/system/
sudo cp infra/systemd/antang-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now antang-backup.timer
systemctl list-timers antang-backup.timer
```

手动跑一次：

```bash
bash scripts/backup-database
```

环境变量可以覆盖默认值：`ANTANG_BACKUP_DIR`、`ANTANG_BACKUP_PASSPHRASE_FILE`、
`ANTANG_BACKUP_KEEP_DAYS`（默认保留 14 天）。清理仅匹配本脚本生成的 `YYYYMMDDTHHMMSSZ` 目录，不清理命名发布备份或其他目录。清理仅匹配本脚本生成的 `YYYYMMDDTHHMMSSZ` 目录，不清理命名发布备份或其他目录。

## 恢复

恢复到一个**临时库**先看一眼，确认没问题再动生产库：

```bash
# 1. 新建一个空库
docker exec antang-prod-postgres-1 psql -U wocky -d postgres \
  -c "CREATE DATABASE antang_restore"

# 2. 解密解压后灌进去
gpg --batch --pinentry-mode loopback \
    --passphrase-file /home/ubuntu/.antang-backup.pass \
    --decrypt 20261018T043000Z/antang.dump.gz.gpg \
  | gunzip \
  | docker exec -i antang-prod-postgres-1 pg_restore -U wocky -d antang_restore

# 3. 抽查
docker exec antang-prod-postgres-1 psql -U wocky -d antang_restore \
  -c "SELECT count(*) FROM users" -c "SELECT count(*) FROM messages"
```

确认无误后，停掉 api 容器再整体替换生产库（`pg_restore --clean --if-exists`），
然后重新启动——迁移脚本会在容器启动时自动跑到最新版本。

## 校验

每次备份会写一个 `SHA256SUMS`。传输或拷贝之后核对一遍：

```bash
cd 20261018T043000Z && sha256sum -c SHA256SUMS
```

## 还没做的

备份只在本机磁盘上，服务器本身挂了就一起没了。下一步应当把加密后的文件同步到对象存储
（腾讯云 COS 或另一台机器）。因为文件已经加密，同步通道不需要是可信的。
