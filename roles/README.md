# Role Manifests

Each YAML file defines a role in the cnb organization. Roles control:
- **commands**: what CLI commands are relevant (primary/secondary/infra tiers)
- **scope**: what resources the role manages
- **boundaries**: what the role explicitly does NOT do

## Role hierarchy

```
Human roles                          Tongxue roles
-----------                          -------------
main_user (owner/operator)           tx_super_admin (cross-machine chief)
admin_user (infrastructure)            tx_device_manager (single machine)
device_user (basic access)               tx_project_manager (single project team)
                                           tx_project_member (task executor)
```

## Usage

- `cnb --help` reads the active role and shows relevant commands
- System prompts are generated from role manifests (not hand-written)
- `cnb roles list` shows all roles; `cnb roles show <role>` shows details
