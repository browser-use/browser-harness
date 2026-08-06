# Invicti API verification (read-only)

Open the docs UI and authenticate:
- https://www.netsparkercloud.com/docs/index

Credentials are required (HTTP Basic Auth) and should be provided via local env vars / `.env`:
- `INVICTI_USER_ID`
- `INVICTI_TOKEN`

Then produce a summary of the following datasets (read-only endpoints):

## Humans
- Current user: `GET /api/1.0/account/me`
- Teams: `GET /api/1.0/team/list`
- Roles: `GET /api/1.0/roles/list`
- Members: `GET /api/1.0/members/list`

## Groups
- AgentGroups: `GET /api/1.0/agentgroups/list`
- Agents: `GET /api/1.0/agents/list`
- WebsiteGroups: `GET /api/1.0/websitegroups/list`
- Websites: `GET /api/1.0/websites/list` (or use `GET /api/1.0/websites/searchlist` / `GET /api/1.0/websites/get` for targeted lookups)

## Stacks
- Technologies: `GET /api/1.0/technologies/list`
- Vulnerability definitions: `GET /api/1.0/vulnerability/list`
- Vulnerability types: `GET /api/1.0/vulnerability/types`

## Correlation ideas
- Join `Members[].RoleWebsiteGroupMappings[]` and `Team[].RoleWebsiteGroupMappings[]` to WebsiteGroups by `WebsiteGroupId` to reason about access scope and website counts.
- Join `AgentGroups[].Agents[]` (agent IDs) to `Agents[].Id`.
- Websites include `Groups` (id+name) which can be correlated to WebsiteGroups.

Optional: export separate CSV files (Members, Teams, Roles, AgentGroups, Agents, WebsiteGroups, Websites, Technologies) and pivot locally.

