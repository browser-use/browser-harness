# DigitalOcean — team bootstrap and partial provisioning

Applies to `cloud.digitalocean.com` and the documented `api.digitalocean.com/v2` API.

## Account and team identity

- Confirm the team and a known project before mutations. The CLI's stored context and
  the browser's selected team can differ. Use an explicit context or credentials for
  the intended team; never infer ownership from the last active shell.
- Organization setup may preselect an eligible team rather than the visible team's
  name. Review team membership and imported billing settings before final submission.

## Capacity and default networks

- Query the live, paginated `/v2/sizes` inventory and check its `regions` list. A valid
  size slug can be unavailable in a region, even when the region is operational.
- A region's first VPC becomes its default. A default VPC cannot be deleted, even when
  empty. Prepare a durable shared default before an environment's disposable VPC.
- To replace a default, designate another VPC in the same region with `default: true`;
  verify the old network is nondefault and empty before its managed replacement.
- Keep a Droplet, its VPC and its reserved IP in the same region. A Spaces bucket can
  retain its separate region when its endpoint configuration remains consistent.
- If a partial apply created a resource that state did not record, identify it through
  the provider API and reconcile ownership before retrying. Do not allocate a duplicate
  or destroy an environment wholesale to recover one failed resource.

## Spaces access keys

- The current Spaces key API supports creation at `POST /v2/spaces/keys`.
  Full-access input uses `grants: [{"bucket": "", "permission": "fullaccess"}]`.
- The response may omit the empty `bucket` property. Normalize that representation;
  an exact comparison with the request object can fail after successful creation.
- Store the once-only returned secret before optional response checks. Do not leave a
  key unrecorded because a non-secret metadata assertion failed.
- Current API reference: https://docs.digitalocean.com/reference/api/reference/spaces-keys/
- Default-network deletion rules:
  https://docs.digitalocean.com/reference/doctl/reference/vpcs/delete/
