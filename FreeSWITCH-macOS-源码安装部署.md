# macOS 本地安装 FreeSWITCH 部署文档

## 1. 环境说明

本次部署目标是在 macOS 本地环境中，将 FreeSWITCH 从源码安装到 `/usr/local` 目录下。

实际安装路径：

```bash
/usr/local/freeswitch
```

源码目录：

```bash
/usr/local/src
```

版本：

```text
FreeSWITCH 1.10.12-release 64bit
```

系统环境：

```text
macOS
Apple Silicon arm64
Homebrew: /opt/homebrew
安装前缀: /usr/local/freeswitch
```

## 2. 创建安装目录

由于 `/usr/local` 默认归 `root` 管理，需要先创建源码目录和安装目录，并调整权限。

```bash
sudo mkdir -p /usr/local/src
sudo mkdir -p /usr/local/freeswitch
sudo chown -R "$USER":staff /usr/local/src /usr/local/freeswitch
```

## 3. 安装编译依赖

使用 Homebrew 安装 FreeSWITCH 编译依赖：

```bash
HOMEBREW_NO_AUTO_UPDATE=1 brew install --only-dependencies freeswitch
```

另外安装构建工具和 PCRE：

```bash
brew install autoconf automake libtool pkgconf pcre
```

## 4. 下载源码

进入源码目录：

```bash
cd /usr/local/src
```

下载 FreeSWITCH 1.10.12：

```bash
curl -LO https://files.freeswitch.org/releases/freeswitch/freeswitch-1.10.12.-release.tar.xz
tar -xf freeswitch-1.10.12.-release.tar.xz
```

下载并解压 spandsp：

```bash
curl -L -o spandsp-3.0.0-0d2e6ac65e.tar.gz \
  https://github.com/freeswitch/spandsp/archive/0d2e6ac65e.tar.gz

tar -xf spandsp-3.0.0-0d2e6ac65e.tar.gz
mv spandsp-0d2e6ac65e* spandsp
```

## 5. 编译安装 spandsp

```bash
cd /usr/local/src/spandsp
```

配置：

```bash
env \
  PKG_CONFIG_PATH=/opt/homebrew/lib/pkgconfig:/opt/homebrew/share/pkgconfig:/opt/homebrew/opt/libtiff/lib/pkgconfig:/opt/homebrew/opt/libpng/lib/pkgconfig:/opt/homebrew/opt/jpeg-turbo/lib/pkgconfig \
  CPPFLAGS=-I/opt/homebrew/include \
  LDFLAGS=-L/opt/homebrew/lib \
  ./configure \
    --prefix=/usr/local/freeswitch/spandsp \
    --disable-silent-rules
```

编译并安装：

```bash
make -j8
make install
```

## 6. 调整 FreeSWITCH 模块配置

进入 FreeSWITCH 源码目录：

```bash
cd /usr/local/src/freeswitch-1.10.12.-release
```

由于当前 macOS/Homebrew 的依赖版本较新，以下两个模块在本机编译时不兼容，因此禁用：

```bash
perl -0pi.bak -e 's/^applications\/mod_av$/#applications\/mod_av/m' modules.conf
perl -0pi.bak -e 's/^databases\/mod_pgsql$/#databases\/mod_pgsql/m' modules.conf
```

说明：

- `mod_av` 与当前 Homebrew FFmpeg API 不兼容。
- `mod_pgsql` 与当前 libpq 头文件在 `-Werror` 下编译失败。

## 7. 配置 FreeSWITCH 编译参数

```bash
env \
  PATH=/opt/homebrew/opt/pkgconf/bin:/opt/homebrew/opt/libtool/libexec/gnubin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  PKG_CONFIG_PATH=/usr/local/freeswitch/spandsp/lib/pkgconfig:/opt/homebrew/opt/pcre/lib/pkgconfig:/opt/homebrew/opt/ffmpeg@7/lib/pkgconfig:/opt/homebrew/opt/openssl@3/lib/pkgconfig:/opt/homebrew/opt/libpq/lib/pkgconfig:/opt/homebrew/opt/sqlite/lib/pkgconfig:/opt/homebrew/opt/jpeg-turbo/lib/pkgconfig:/opt/homebrew/lib/pkgconfig:/opt/homebrew/share/pkgconfig \
  CPPFLAGS="-I/opt/homebrew/opt/pcre/include -I/opt/homebrew/include -I/opt/homebrew/opt/jpeg-turbo/include" \
  LDFLAGS="-L/opt/homebrew/opt/pcre/lib -L/opt/homebrew/lib -L/opt/homebrew/opt/jpeg-turbo/lib" \
  ./configure \
    --prefix=/usr/local/freeswitch \
    --exec_prefix=/usr/local/freeswitch \
    --enable-shared \
    --enable-static \
    --disable-libvpx
```

配置完成后，关键路径如下：

```text
prefix:     /usr/local/freeswitch
confdir:    /usr/local/freeswitch/etc/freeswitch
modulesdir: /usr/local/freeswitch/lib/freeswitch/mod
soundsdir:  /usr/local/freeswitch/share/freeswitch/sounds
```

## 8. 编译并安装 FreeSWITCH

```bash
make -j8
make install
```

安装成功后会出现：

```text
FreeSWITCH install Complete
```

## 9. 安装声音包和 MOH 音乐

```bash
make cd-sounds-install cd-moh-install
```

安装完成后，声音目录位于：

```bash
/usr/local/freeswitch/share/freeswitch/sounds
```

包含：

```text
en/us/callie
music/8000
music/16000
music/32000
music/48000
```

## 10. 修复 fs_cli 连接端口问题

默认 `fs_cli` 使用 `127.0.0.1:8021` 连接 FreeSWITCH。

本机 macOS 上 `8021` 被 `launchd` 预占，因此 FreeSWITCH 的 `mod_event_socket` 无法监听该端口。

修改配置文件：

```bash
vi /usr/local/freeswitch/etc/freeswitch/autoload_configs/event_socket.conf.xml
```

将配置改为：

```xml
<configuration name="event_socket.conf" description="Socket Client">
  <settings>
    <param name="nat-map" value="false"/>
    <param name="listen-ip" value="127.0.0.1"/>
    <param name="listen-port" value="8022"/>
    <param name="password" value="ClueCon"/>
    <!--<param name="apply-inbound-acl" value="loopback.auto"/>-->
    <!--<param name="stop-on-bind-error" value="true"/>-->
  </settings>
</configuration>
```

## 11. 配置 fs_cli 默认连接参数

创建用户级配置文件：

```bash
vi ~/.fs_cli_conf
```

内容：

```text
[default]
host => 127.0.0.1
password => ClueCon
port => 8022
```

这样之后可以直接运行：

```bash
fs_cli
```

不需要每次手动加：

```bash
-P 8022
```

## 12. 创建命令符号链接

将 FreeSWITCH 常用命令链接到 `/usr/local/bin`：

```bash
sudo ln -s /usr/local/freeswitch/bin/freeswitch /usr/local/bin/freeswitch
sudo ln -s /usr/local/freeswitch/bin/fs_cli /usr/local/bin/fs_cli
sudo ln -s /usr/local/freeswitch/bin/fs_encode /usr/local/bin/fs_encode
sudo ln -s /usr/local/freeswitch/bin/fs_tts /usr/local/bin/fs_tts
sudo ln -s /usr/local/freeswitch/bin/fsxs /usr/local/bin/fsxs
sudo ln -s /usr/local/freeswitch/bin/gentls_cert /usr/local/bin/gentls_cert
sudo ln -s /usr/local/freeswitch/bin/tone2wav /usr/local/bin/tone2wav
sudo ln -s /usr/local/freeswitch/bin/switch_eavesdrop /usr/local/bin/switch_eavesdrop
```

验证：

```bash
command -v freeswitch
command -v fs_cli
```

输出应为：

```text
/usr/local/bin/freeswitch
/usr/local/bin/fs_cli
```

## 13. 启动 FreeSWITCH

推荐启动命令：

```bash
freeswitch -ncwait -nonat -np
```

参数说明：

```text
-ncwait  后台启动，并等待系统 ready
-nonat   禁用 NAT 自动检测
-np      普通优先级，避免 macOS 普通用户启动时报 Could not set nice level
```

启动成功输出类似：

```text
System Ready pid:55103
```

## 14. 连接 FreeSWITCH CLI

```bash
fs_cli
```

或执行单条命令：

```bash
fs_cli -x status
```

正常输出：

```text
FreeSWITCH (Version 1.10.12 -release 64bit) is ready
```

## 15. 停止 FreeSWITCH

方式一，通过 `fs_cli`：

```bash
fs_cli
```

进入后执行：

```text
shutdown
```

方式二，通过命令行：

```bash
freeswitch -stop
```

## 16. 当前安装验证结果

版本验证：

```bash
freeswitch -version
```

输出：

```text
FreeSWITCH version: 1.10.12-release~64bit (-release 64bit)
```

CLI 连接验证：

```bash
fs_cli -x status
```

输出：

```text
FreeSWITCH (Version 1.10.12 -release 64bit) is ready
```

event socket 监听验证：

```bash
netstat -anv | grep 8022
```

应看到：

```text
127.0.0.1.8022 LISTEN freeswitch
```

## 17. 已安装的主要组件

安装目录：

```bash
/usr/local/freeswitch
```

主要二进制：

```text
/usr/local/freeswitch/bin/freeswitch
/usr/local/freeswitch/bin/fs_cli
/usr/local/freeswitch/bin/fs_encode
/usr/local/freeswitch/bin/fs_tts
/usr/local/freeswitch/bin/fsxs
```

主要配置目录：

```bash
/usr/local/freeswitch/etc/freeswitch
```

模块目录：

```bash
/usr/local/freeswitch/lib/freeswitch/mod
```

声音目录：

```bash
/usr/local/freeswitch/share/freeswitch/sounds
```

日志目录：

```bash
/usr/local/freeswitch/var/log/freeswitch
```

运行目录：

```bash
/usr/local/freeswitch/var/run/freeswitch
```

## 18. 注意事项

本次部署中禁用了以下模块：

```text
applications/mod_av
databases/mod_pgsql
```

原因：

```text
mod_av: 当前 Homebrew FFmpeg API 与 FreeSWITCH 1.10.12 源码不兼容
mod_pgsql: 当前 libpq 头文件触发 -Werror 编译失败
```

`fs_cli` 使用的 event socket 端口已从默认 `8021` 改为：

```text
8022
```

原因：

```text
macOS launchd 已经占用 8021
```

当前没有配置 launchd 开机自启服务，FreeSWITCH 需要手动启动：

```bash
freeswitch -ncwait -nonat -np
```
