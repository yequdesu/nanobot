---
name: service_explorer
description: "Discover and execute commands on remote microservices via Nacos. Use remote_exec tool to call weather, calculator, time services and more."
metadata:
  nanobot:
    emoji: "🌐"
    requires:
      tools: ["remote_exec"]
---

# Service Explorer Skill

Use this skill to discover and interact with remote microservices registered in Nacos.

## Available Services

| Service | Description | Example Commands |
|---------|-------------|------------------|
| weather-service | Weather information | `check Beijing`, `forecast Shanghai --days 3` |
| calculator-service | Math operations | `add 10 20`, `mul 5 6`, `div 100 4` |
| time-service | Time utilities | `now`, `date`, `timestamp`, `weekday` |

## Workflow

Always follow this 2-step process:

### Step 1: Explore with --help

First, discover what commands a service supports:

```
remote_exec(service_name="weather-service", command_line="--help")
```

### Step 2: Execute Actual Command

After understanding available commands, execute the real command:

```
remote_exec(service_name="weather-service", command_line="check Beijing")
```

## Examples

### Weather Query

1. Explore:
   ```
   remote_exec(service_name="weather-service", command_line="--help")
   ```

2. Execute:
   ```
   remote_exec(service_name="weather-service", command_line="check Shanghai")
   ```

### Calculator

1. Explore:
   ```
   remote_exec(service_name="calculator-service", command_line="--help")
   ```

2. Execute:
   ```
   remote_exec(service_name="calculator-service", command_line="add 100 50")
   ```

### Time Utilities

1. Explore:
   ```
   remote_exec(service_name="time-service", command_line="--help")
   ```

2. Execute:
   ```
   remote_exec(service_name="time-service", command_line="now")
   ```

## Error Handling

- If service not found: Check service name spelling
- If command fails: Use `--help` to see correct usage
- If timeout: Service may be down, try again later

## Best Practices

1. Always start with `--help` for unfamiliar services
2. Check command output format before parsing
3. Handle stderr messages appropriately
4. Use specific service for specific tasks (don't use calculator for time)
