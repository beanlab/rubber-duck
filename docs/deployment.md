# AWS production deployment

Rubber Duck production runs on one Terraform-managed EC2 instance and is deployed from GitHub Actions through AWS Systems Manager (SSM). The instance has no public IP, inbound security-group rules, SSH key, or static AWS credentials.

## Production environment

| Setting | Value |
|---|---|
| Git branch | `master` |
| Environment | `production` |
| AWS account | `844825014198` |
| Region | `us-west-2` |
| VPC | `vpc-0d5da450de7b3e1ee` |
| Private subnet | `subnet-0a49a0288c57235e1` |
| Instance type | `t3.small` |
| Ubuntu AMI | `ami-026ec9e84a2221297` |
| ECR repository | `beanlab/rubber-duck` |
| Configuration | `s3://rubber-duck-config/environments/production/config.yaml` |
| Runtime secret | `/rubber-duck/production/runtime` |

The AMI is deliberately pinned. Updating its ID in `aws/terraform/environment/environments/production.tfvars` replaces the instance while retaining the persistent data volume.

## Architecture

- `aws/terraform/bootstrap`: shared state bucket, GitHub OIDC provider, and GitHub deployment role.
- `aws/terraform/environment`: EC2, IAM instance profile, security group, persistent EBS volume, and secret container.
- `aws/scripts`: scripts installed on the instance by cloud-init.
- `.github/workflows/ci-cd.yml`: build, provision, host maintenance, and deployment pipeline.

SQLite is stored at `/var/lib/rubber-duck/rubber-duck.db` on the persistent EBS volume and mounted into the container as `/rubber-duck.db`.

## One-time bootstrap

Bootstrap requires Terraform 1.10 or newer, AWS CLI, `jq`, and an administrator-capable AWS profile. It creates new resources but does not interact with the old production instance.

Create a local JSON file containing Docker environment values:

```json
{
  "DISCORD_TOKEN": "...",
  "OPENAI_API_KEY": "..."
}
```

Additional single-line string values may be included when required. Protect the file and run bootstrap:

```bash
chmod 600 /private/path/production-runtime.json
./aws/first-time-bootstrap.sh \
  --profile byu-cs-poweruser \
  --secrets /private/path/production-runtime.json \
  --config production-config.yaml
```

The command:

1. validates account `844825014198` and region `us-west-2`
2. creates/imports the Terraform state bucket and existing GitHub OIDC provider
3. creates the bounded GitHub deployment role
4. provisions the new production environment
5. writes runtime values directly to Secrets Manager
6. uploads the production configuration object

Secret values never enter Terraform state or S3. Keep the local JSON file outside the repository. Bootstrap is rerunnable: if it stops after infrastructure creation, correct the reported error and run the same command again. A successful run verifies that the runtime secret has an `AWSCURRENT` value and that the configuration object exists before reporting completion.

Before applying, plans can be reviewed manually from each Terraform root using the backend and variables shown in `aws/first-time-bootstrap.sh`.

## Normal deployment

A push to `master`, or a manual dispatch from `master`, runs one serialized workflow:

1. validate the explicit `master -> production` mapping
2. build with the current Python 3.12 base image
3. label and tag the image with the full commit SHA
4. push it to ECR and resolve its digest
5. apply production Terraform
6. wait for cloud-init and SSM
7. update host packages and reboot when required
8. deploy the exact ECR digest through SSM
9. require the container to remain running for 30 seconds
10. report environment, commit, tag, digest, AMI, and instance ID

The production container is named `rubber-duck-production`. Release metadata is written to `/var/lib/rubber-duck/release.json`.

## Diagnostics

Find the Terraform-managed instance:

```bash
aws --profile byu-cs-poweruser --region us-west-2 ec2 describe-instances \
  --filters Name=tag:Application,Values=rubber-duck Name=tag:Environment,Values=production \
  --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name,Name:Tags[?Key==`Name`]|[0].Value}'
```

Use Session Manager rather than SSH:

```bash
aws --profile byu-cs-poweruser --region us-west-2 ssm start-session \
  --target INSTANCE_ID
```

Useful instance-side commands:

```bash
sudo docker ps -a
sudo docker logs --tail 200 rubber-duck-production
sudo cat /var/lib/rubber-duck/release.json
findmnt /var/lib/rubber-duck
cloud-init status --long
```

GitHub prints complete SSM invocation details when maintenance or deployment fails.

## Rollback

There is no automatic rollback or arbitrary-commit workflow input. To redeploy previous source behavior:

1. revert the unwanted change on `master`
2. push the revert so the normal production workflow rebuilds and deploys it
3. verify the reported ECR digest and release metadata

Each run rebuilds dependencies and the base image, so the digest—not only the source tag—identifies the exact artifact.

## Manual database cutover

The replacement volume intentionally starts empty. Do not run the old and new production bots simultaneously with the same Discord token.

At the coordinated cutover:

1. manually stop the old `duck` container
2. make a consistent copy of `/home/ubuntu/rubber-duck.db` from the old host
3. stop `rubber-duck-production` if it has created an empty database
4. place the copied database at `/var/lib/rubber-duck/rubber-duck.db` on the new host
5. set ownership and permissions appropriate for the root-run container
6. rerun the GitHub deployment and verify bot behavior and stored records
7. take the old instance offline manually only after verification

Terraform and the deployment workflow never target, stop, or replace the old instance `i-0e82640083109edf2`.

## Security notes

- GitHub uses OIDC role assumption; no AWS access-key secrets are required.
- The application uses its EC2 instance profile from inside Docker.
- The host Docker socket is mounted intentionally because configured Python tools launch short-lived sibling sandbox containers. This grants the application root-equivalent control of the new host and is a known trust boundary; no unrelated workloads should run there.
- Runtime values are fetched from Secrets Manager into a temporary root-only file and removed on every exit.
- The security group has no ingress. Outbound traffic uses the private subnet's NAT gateway.
- The persistent volume has Terraform deletion protection.
