<!-- cnb:start -->
## Multi-Agent Coordination

This project uses cnb for multi-session coordination.

### Session Startup

You are a session. Your name is passed via `--name` when Claude Code starts.
On startup:
```bash
/Users/zhangkezhen/Desktop/claudes-code/bin/board --as <your-name> inbox
```

### Commands

```bash
/Users/zhangkezhen/Desktop/claudes-code/bin/board --as <name> send <to> "<msg>"    # message (person or "all")
/Users/zhangkezhen/Desktop/claudes-code/bin/board --as <name> inbox                # check unread
/Users/zhangkezhen/Desktop/claudes-code/bin/board --as <name> ack                  # clear inbox
/Users/zhangkezhen/Desktop/claudes-code/bin/board --as <name> status "<desc>"      # update current task
/Users/zhangkezhen/Desktop/claudes-code/bin/board --as <name> task add "<desc>"    # add task
/Users/zhangkezhen/Desktop/claudes-code/bin/board --as <name> task done            # finish current task
/Users/zhangkezhen/Desktop/claudes-code/bin/board --as <name> view                 # board overview
/Users/zhangkezhen/Desktop/claudes-code/bin/board --as <name> bug report P1 "desc" # report bug
/Users/zhangkezhen/Desktop/claudes-code/bin/board --as <name> send all "msg"       # broadcast
```

### Rules

- Check inbox at startup and after completing each task.
- Update status when you start or finish work.
- Commit immediately after each logical change.
- Message others via `send`, not by editing their files.

### Sessions

- **sutskever**
- **lecun**
- **lisa-su**
<!-- cnb:end -->
