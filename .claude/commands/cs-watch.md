看某个同学在干什么。解析 $ARGUMENTS 拿到名字。
运行 `tmux capture-pane -t cc-26d5-<名字> -p -S -30 2>/dev/null | tail -20`，用简洁的话告诉用户这个同学在做什么、进展到哪了。
