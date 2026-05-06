查看指定同学当前在做什么。解析 $ARGUMENTS 拿到名字。

1. 先用 `/Users/zhangkezhen/Desktop/claudes-code/bin/board --as lead view` 看该同学的状态
2. 然后运行 `tmux capture-pane -t $(grep '^prefix' .claudes/config.toml | cut -d'"' -f2)-<名字> -p -S -30 2>/dev/null | tail -20` 看该同学终端的最近输出
3. 把结果用简洁的方式汇总给用户：在做什么、进展到哪了
