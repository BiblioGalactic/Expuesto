# ControlRoom Integration

## Config file
- Edit `controlroom.config.json` at project root.
- Main flags:
  - `featureFlags.controlRoomEnabled`
  - `ui.defaultView`
  - `ui.rememberLastView`

## Service commands
- Commands are executed in safe argv mode (`program` + `args`).
- No implicit shell execution is used by the backend.

## New Tauri commands
- `controlroom_load_config`
- `controlroom_get_services`
- `controlroom_service_start`
- `controlroom_service_stop`
- `controlroom_service_restart`
- `controlroom_service_status`
- `controlroom_service_status_all`
- `controlroom_service_clear_logs`
- `controlroom_runner_execute`
- `controlroom_runner_cancel`
- `controlroom_workspace_list`
- `controlroom_git_commits`
- `controlroom_export_logs`

## New events
- `controlroom://service-log`
- `controlroom://service-state`
- `controlroom://runner-output`
- `controlroom://runner-exit`
- `controlroom://backend-error`

## Run
1. `pnpm install`
2. `pnpm test`
3. `pnpm tauri dev`

If `controlRoomEnabled=false`, app falls back to classic shell view.
