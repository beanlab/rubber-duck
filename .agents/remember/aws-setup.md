# AWS EC2 environment provisioning and deployment plan

## Purpose

This is the implementation handoff for replacing Rubber Duck's partially manual AWS deployment with Terraform-provisioned EC2 environments and SSM-based Docker deployment.

The initial implementation should stay narrow and pragmatic:

- production first, deployed from `master`
- additional environments deferred until production automation works
- no inbound network access
- GitHub OIDC instead of static AWS credentials
- host security updates during code deployment
- manual AMI upgrades when desired
- Docker images clearly traceable to their source commit
- persistent data outside the replaceable EC2 root volume

## Current repository state

Planning was done on the `infra` branch.

At the time this plan was written, `aws/restart_duck.sh` was newly added/staged and then modified. It contains the user's current manual server deployment procedure. Before editing it, inspect `git status`, the staged diff, and the unstaged diff so the user's work is preserved.

The current deployment works as follows:

- `.github/workflows/ci-cd.yml` runs on `master`.
- `.github/scripts/build_docker.sh` builds from an inline Dockerfile.
- GitHub Actions pushes an image to ECR.
- GitHub Actions creates an environment file containing secrets and AWS credentials and uploads it to S3.
- GitHub Actions uploads a production configuration file to S3.
- `aws/restart_duck.sh` is manually edited and run on the EC2 server to select an image, replace the container, and prune old images.
- The application mounts `/home/ubuntu/rubber-duck.db` for SQLite persistence.
- The application mounts `/var/run/docker.sock` because it launches sibling tool containers.

## Target deployment flow

For every push to an explicitly configured deployment branch:

1. Map the branch to a canonical environment name.
2. Build the Docker image from that commit.
3. Tag and label the image with the full Git commit SHA.
4. Push the image to ECR.
5. Run Terraform for the mapped environment.
6. Create the environment if it does not exist, or update it if it does.
7. Wait for the instance to finish bootstrap and become available through SSM.
8. Run host software updates through SSM.
9. Reboot if updates require it, then wait for SSM to return.
10. Deploy the exact pushed Docker image by ECR digest through SSM.
11. Verify that the container remains running for a bounded startup period.
12. Report the environment, commit, human-readable image tag, deployed digest, AMI ID, instance ID, and deployment result.

A normal application deployment is also the host maintenance window. There is no separate host patch scheduler in the initial design.

## Settled decisions

### Explicit branch-to-environment mapping

Do not implement a general branch-name sanitizer in the first version. The initial workflow should contain one explicit mapping:

| Git branch | Environment | Purpose |
|---|---|---|
| `master` | `production` | Initial and production deployment |

Only `master` can provision or deploy in the initial implementation. An arbitrary branch must not create infrastructure. Additional explicit branch-to-environment mappings can be added after production automation works.

Use the canonical environment name everywhere downstream:

- Terraform state key
- AWS resource names and tags
- Secrets Manager path
- S3 configuration prefix
- container name
- GitHub concurrency group

If more dynamic branch environments are needed later, add a consistent `slug + stable hash` scheme then. Do not build that system now.

### Environment lifecycle

- A push to a mapped branch creates the environment if necessary.
- Do not automatically destroy infrastructure when a branch is deleted.
- A protected manual destroy workflow is post-MVP.
- Any future destroy workflow must refuse to destroy `production` without an explicit production override.

### Operating system and AMI updates

- Use an official Canonical Ubuntu Server 26.04 LTS AMD64 AMI.
- Trust only Canonical AWS owner ID `099720109477`.
- Store the selected AMI ID as an explicit Terraform variable or environment configuration value.
- Do not automatically resolve and adopt the latest AMI on every deployment.
- Host security updates through `apt` are sufficient for routine maintenance.
- AMI upgrades are manual: update the configured AMI ID, then run the normal CI/CD deployment. Terraform will replace the instance when that value changes.
- Record the deployed AMI ID in Terraform outputs and GitHub deployment logs.

This avoids coupling every application push to EC2 replacement while still making AMI upgrades repeatable through the same CI/CD path.

Before the first implementation deployment, select and verify an official Ubuntu 26.04 AMI in `us-west-2` and record its ID in the environment configuration.

### Host update policy

Do not initially use:

- AWS Patch Manager
- a separate patch scheduler
- unattended automatic reboots
- workstation-run maintenance commands

Every code deployment should run one instance-side update script through SSM:

```bash
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get full-upgrade -y
apt-get autoremove -y
apt-get clean
```

Use Ubuntu's `docker.io` package and the SSM agent supplied by the official Canonical AMI. Let the normal operating-system package mechanisms handle updates; do not add separate Docker-repository or Snap-versus-deb update branches initially.

The script should emit exactly `reboot-required=true` or `reboot-required=false`. If a reboot is required, the workflow should reboot the instance and wait for SSM to reconnect before deploying the application.

The instance bootstrap script should not also perform a full host upgrade. There should be one observable owner for package upgrades: `update-host.sh`.

### Networking

- No inbound security-group rules.
- No SSH and no EC2 key pair.
- Administration and deployment use SSM only.
- The instance requires outbound access for Discord, OpenAI, ECR, S3, SSM, Ubuntu repositories, and application AWS APIs.
- Use the approved account VPC and public subnet; do not assume a default VPC exists.

The autograder reference currently uses:

- region `us-west-2`
- VPC `vpc-057175f829f9e74b2`
- subnet `subnet-050f8f212a3bee8a8`

Confirm these are the intended Rubber Duck network values before committing them as CI variables or Terraform configuration.

### Enterprise AWS account constraints

The current account context is:

- AWS account ID `844825014198`
- required IAM permissions boundary:
  `arn:aws:iam::844825014198:policy/iamRolePermissionBoundary`
- standard GitHub Actions OIDC provider may already exist and may need to be imported
- no assumption of a default VPC or default security group

Follow the proven autograder import/bootstrap pattern for existing enterprise-managed resources.

### Docker source traceability

Clear traceability to source code is more important than strict tag immutability.

For every build:

- Use the full Git commit SHA, never a five-character SHA.
- Tag the image as `<environment>-<full-commit-sha>`.
- Add standard OCI labels, including:
  - `org.opencontainers.image.revision=<full-commit-sha>`
  - `org.opencontainers.image.source=<repository-url>`
  - `org.opencontainers.image.created=<build-timestamp>`
- Record the branch/environment as an additional label.
- After pushing, resolve and report the ECR image digest.
- Deploy `repository@sha256:<digest>` so the server runs the exact image produced by that workflow.
- Retain the full-SHA tag as the human-readable source identifier.
- Persist the deployed commit, tag, and digest in a small release metadata file on the instance.

A workflow rerun may rebuild the same commit with newer base-image or dependency artifacts. That is acceptable for this project because the tag and labels still identify the source commit. Recording the resulting digest preserves the ability to distinguish exact builds when needed.

Replace the inline Dockerfile with:

- top-level `Dockerfile`
- top-level `.dockerignore`

Build with `--pull` so each code deployment incorporates the current `python:3.12` base image. Host updates do not update packages inside the container, so rebuilding is also the container maintenance mechanism.

Optional convenience tags such as `production-latest` are not needed in the first version.

### Secrets and AWS credentials

- GitHub Actions uses OIDC, not long-lived AWS access keys.
- The EC2 instance uses an IAM instance profile.
- Do not put `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` into the application environment.
- Do not upload generated runtime secret files to S3.
- Store runtime secrets in Secrets Manager at:
  `/rubber-duck/<environment>/runtime`.
- Terraform may create the secret container, but secret values must not pass through Terraform variables or state.
- Populate secret values separately with a small bootstrap command patterned after the autograder.
- The deployment script fetches the secret using the instance role, creates a temporary root-readable Docker environment file, and deletes it with a `trap`.

An environment must have its secret and configuration populated before its branch is enabled in the deployment workflow.

Initial enablement order:

1. Provision or identify the environment secret.
2. Write secret values directly to Secrets Manager.
3. Create the environment configuration object in S3.
4. Add or enable the branch mapping in the workflow.
5. Run deployment.

Concurrent environments need intentionally appropriate Discord tokens and channel configuration. Do not accidentally run test and production against the same production Discord setup.

### Application configuration

Use one simple S3 configuration object per environment:

```text
s3://rubber-duck-config/environments/<environment>/config.yaml
```

- Pass this exact URI to the container as `CONFIG_FILE_S3_PATH`.
- Do not create commit-specific configuration snapshots or configuration rollback machinery in the initial implementation.
- Remove unused workflow-dispatch inputs.
- Do not assume a path stored in a GitHub secret refers to a file available on a fresh GitHub runner.

### Persistent data

The SQLite database must not live on the replaceable root volume.

For each environment:

- Create one environment-specific EBS data volume.
- Mount it at `/var/lib/rubber-duck`.
- Store the database at `/var/lib/rubber-duck/rubber-duck.db`.
- Bind mount it into the container at the application's expected path, currently `/rubber-duck.db`.

When the AMI is manually changed, Terraform may replace the EC2 instance. The data volume must survive that replacement and attach to the new instance.

Some deployment downtime is acceptable. Zero-downtime replacement is out of scope.

Plan and document a one-time production migration from `/home/ubuntu/rubber-duck.db` to the managed production EBS volume.

### Deployment health and rollback

Keep the first implementation narrow:

- The deployment script stops and removes the old container.
- It starts the new container with `--restart unless-stopped`.
- Health means `docker inspect` reports the container running throughout a fixed startup window, initially 30 seconds.
- On failure, print recent container logs and fail the SSM command.
- Do not claim this proves Discord-level application health.
- Do not implement automatic rollback in the first milestone.

The previous image can be redeployed through workflow dispatch if necessary. More sophisticated rollback should wait until there is a meaningful application health signal.

## Terraform structure

Use two Terraform roots only:

```text
aws/
  terraform/
    bootstrap/
      main.tf
      variables.tf
      outputs.tf
    environment/
      main.tf
      variables.tf
      outputs.tf
  scripts/
    instance-bootstrap.sh
    update-host.sh
    deploy-container.sh
    health-check.sh
```

Start with these files and split them only when they become difficult to navigate.

### Bootstrap root

The bootstrap root is rarely run and initially requires administrator credentials from a local machine because the GitHub role cannot create itself.

Use this exact bootstrap sequence, following the autograder pattern:

1. A bootstrap shell script checks for the state bucket and creates it with AWS CLI if it is absent.
2. Initialize the bootstrap Terraform root directly against that S3 backend with S3-native locking.
3. Import the state bucket's Terraform-managed resources and the existing GitHub OIDC provider when present.
4. Apply the remaining shared resources, including the GitHub deployment role.
5. After bootstrap, GitHub Actions runs only the environment Terraform root for routine deployment.

Do not create temporary local Terraform state that later requires migration.

Shared resources and ownership:

| Resource | Initial treatment |
|---|---|
| Terraform state bucket | Terraform-managed after creation/import; encrypted and versioned with S3-native locking |
| GitHub OIDC provider | Import and manage if it already exists |
| GitHub deployment role | Terraform-managed with required permissions boundary |
| Existing ECR repository | Prefer reference as an external data source initially; do not recreate it |
| Existing configuration bucket | Prefer reference as an external data source initially; do not recreate it |

If ownership changes later, make that an explicit migration rather than allowing Terraform to adopt resources accidentally.

### Environment root

Keep reviewable, non-secret production inputs in:

```text
aws/terraform/environment/environments/production.tfvars
```

This file should contain the verified account ID, region, VPC ID, subnet ID, AMI ID, instance type, ECR repository, and configuration bucket. Add another tfvars file only when another environment is deliberately introduced.

Each environment receives:

- state key:
  `rubber-duck/environments/<environment>/terraform.tfstate`
- Ubuntu EC2 instance using the configured AMI ID
- no-ingress security group
- IAM role and instance profile with the enterprise permissions boundary
- persistent EBS data volume and attachment
- environment Secrets Manager secret container if it does not already exist
- tags including `Environment`, `Application=rubber-duck`, and `ManagedBy=terraform`

Outputs should include:

- environment
- instance ID
- AMI ID
- volume ID
- runtime secret ARN/name
- configuration URI or prefix

### Instance role permissions

Grant only required permissions:

- `AmazonSSMManagedInstanceCore`
- ECR authentication and image-pull operations
- read access to the Rubber Duck ECR repository
- read access to the environment's S3 configuration path
- read access to the environment's Secrets Manager secret
- other application S3 or SES permissions demonstrated by the code/configuration

The application should use the instance profile from inside the container. Configure IMDSv2 as required and use an appropriate metadata hop limit for bridge-networked Docker containers, then verify boto3 credential discovery from inside the deployed container.

### GitHub deployment role

The OIDC trust policy should be limited to this repository and intended refs.

The role needs permissions to:

- read/write relevant Terraform state and lock objects
- manage the environment Terraform resources
- push images to the existing ECR repository
- send and inspect SSM commands
- read EC2 and SSM state needed by deployment

Use the autograder bootstrap pattern, but do not copy its broad `Action = "*"` deployment policy unchanged if a practical least-privilege policy can be defined.

## Instance scripts

### `aws/scripts/instance-bootstrap.sh`

Terraform should render a multipart cloud-init document that installs `instance-bootstrap.sh`, `update-host.sh`, `deploy-container.sh`, and `health-check.sh` with root ownership. Terraform should pass the expected EBS volume ID and fixed environment settings into cloud-init.

The Ubuntu-compatible bootstrap script should be idempotent and should only make the node manageable:

1. Wait for package-manager locks if needed.
2. Install Ubuntu's `docker.io` package and required utilities.
3. Ensure the Canonical AMI's SSM agent is enabled and running.
4. Create application directories.
5. Resolve the Terraform-provided EBS volume ID through `/dev/disk/by-id/`; fail rather than guessing if it cannot be identified.
6. Format it only when `blkid` reports no filesystem.
7. Mount it at `/var/lib/rubber-duck`.
8. Add it to `/etc/fstab` by filesystem UUID.
9. Write root-owned fixed settings under `/etc/rubber-duck/`, including `environment`, `config-uri`, and `secret-id`.
10. Configure Docker to start at boot.
11. Configure bounded journald retention.

Do not embed secret values, select an application image, or perform a full system upgrade here.

### `aws/scripts/update-host.sh`

This script is the single owner of routine host package updates.

It should:

1. Run apt update/full-upgrade/autoremove/clean noninteractively.
2. Let the configured Ubuntu package mechanisms update installed packages.
3. Detect `/var/run/reboot-required`.
4. Emit exactly `reboot-required=true` or `reboot-required=false` without treating a required reboot as a failure.

### `aws/scripts/deploy-container.sh`

Suggested interface:

```text
deploy-container.sh <image-digest-uri> <commit-sha> <human-readable-tag>
```

The script reads the environment, configuration URI, and secret ID from root-owned files under `/etc/rubber-duck/`.

The script should:

1. Validate inputs and fixed instance settings.
2. Acquire a `flock` deployment lock.
3. Authenticate Docker to ECR using the instance profile.
4. Pull the exact `repository@sha256:<digest>` image reference.
5. Record the supplied source commit, human-readable full-SHA tag, and deployed digest.
6. Fetch the environment runtime secret from Secrets Manager.
7. Create a temporary root-owned Docker env file.
8. Stop and remove the existing environment container.
9. Start the replacement with:
   - deterministic environment-specific container name
   - `--restart unless-stopped`
   - temporary runtime env file
   - explicit `CONFIG_FILE_S3_PATH`
   - persistent SQLite bind mount
   - `/var/run/docker.sock:/var/run/docker.sock`
10. Run `health-check.sh`.
11. On failure, print recent logs and return nonzero.
12. On success, write commit, tag, digest, config URI, and deployment timestamp to a root-owned release metadata file.
13. Remove temporary secrets on all exits.
14. Prune unused Docker images after success.

### `aws/scripts/health-check.sh`

For the initial version:

- accept the container name
- wait up to 30 seconds
- require the container to remain in Docker's running state
- print container status and recent logs on failure

## GitHub Actions design

Rewrite `.github/workflows/ci-cd.yml` instead of extending its current production-specific job chain.

### Trigger and mapping

The workflow should trigger only on mapped deployment branches and manual dispatch.

The initial workflow should map only:

```text
refs/heads/master -> production
```

Any other ref must fail or skip before AWS mutation. Add other explicit mappings only after the production deployment is working.

### Permissions and concurrency

Use GitHub OIDC:

```yaml
permissions:
  contents: read
  id-token: write
```

Define one workflow-level concurrency group spanning build through deploy:

```yaml
concurrency:
  group: rubber-duck-${{ environment }}
  cancel-in-progress: false
```

The exact GitHub expression may require placing concurrency after the environment has been derived or using the branch ref directly. There should be one conceptual workflow serialization mechanism. Keep `flock` only as defense against out-of-band SSM commands.

### `prepare` job

Produce lowercase, consistently named outputs:

- branch
- environment
- full commit SHA
- image tag
- image URI
- Terraform state key
- configuration URI

Do not retain the current inconsistent output names such as `Short_SHA` versus `short_sha`.

### `build` job

- Checkout the exact commit.
- Configure AWS credentials through OIDC.
- Log in to ECR.
- Build from the committed `Dockerfile` with `--pull`.
- Add source-revision OCI labels.
- Tag `<environment>-<full-sha>`.
- Push the image.
- Resolve the ECR digest and expose it as a job output.

### `provision` job

- Install Terraform.
- Configure AWS credentials through OIDC.
- Verify expected AWS account and region.
- Initialize the environment root with the environment-specific S3 state key and S3-native locking.
- Run `terraform fmt -check` and `terraform validate`.
- Plan and apply using `aws/terraform/environment/environments/production.tfvars`, the explicit environment mapping, and the configured AMI ID.
- Export instance ID and AMI ID.

A normal deployment should not replace the EC2 instance merely because a newer Canonical image exists. Replacement happens when the configured AMI ID is intentionally changed.

### `maintain` job

- Wait for cloud-init/bootstrap completion and SSM registration.
- Run `update-host.sh` through SSM.
- Poll command status and print stdout/stderr on failure.
- If reboot is required, reboot through SSM.
- Wait for the node to go offline and then return online.

### `deploy` job

- Invoke `deploy-container.sh` through SSM with the digest URI, commit SHA, and human-readable full-SHA tag.
- Poll with a bounded timeout.
- Print SSM output and container logs on failure.
- Report environment, branch, commit, tag, deployed digest, AMI ID, instance ID, and result.

Discord deployment notifications may be restored after the core workflow works, but they should not sit on the critical path between build and deployment.

## Secret and environment bootstrap tooling

Provide a small local bootstrap command patterned after the autograder:

- require an administrator AWS profile
- validate account and region
- require a protected local dotenv or JSON file with mode `600` or `400`
- create/import shared Terraform resources
- write runtime secret values directly to Secrets Manager after Terraform apply
- never pass secret values to Terraform

Routine infrastructure and application deployments must run through GitHub after this one-time bootstrap.

## Implementation milestones

### Milestone 1: production automation

1. Add `Dockerfile` and `.dockerignore`.
2. Simplify or replace `.github/scripts/build_docker.sh`.
3. Create the two Terraform roots and `production.tfvars`.
4. Bootstrap/import the state bucket, OIDC provider, and GitHub deployment role using the documented remote-state sequence.
5. Configure and verify the explicit Ubuntu 26.04 AMI ID, VPC, subnet, ECR repository, and configuration bucket.
6. Add the production EC2, IAM, no-ingress security group, EBS, and secret-container resources.
7. Deliver bootstrap, update, deployment, and health scripts through Terraform-rendered cloud-init.
8. Populate the production runtime secret and `environments/production/config.yaml`.
9. Migrate `/home/ubuntu/rubber-duck.db` to the managed production EBS volume.
10. Rewrite the workflow with only the `master -> production` mapping.
11. Deploy production through GitHub Actions.
12. Remove obsolete short-SHA tagging, static AWS credentials, S3 secret-file upload, and hard-coded manual restart behavior after the automated path succeeds.
13. Update `docs/deployment.md` and the README deployment summary.

Milestone 1 is successful when four observable proofs pass:

1. GitHub OIDC provisions production; the instance has no ingress or SSH key and is reachable through SSM.
2. The exact digest-pinned image starts using Secrets Manager, the fixed production S3 configuration, and the instance role; its full-SHA tag and OCI labels trace it to source.
3. Host updates and any required reboot complete before the 30-second container-running check.
4. A deliberate EC2 replacement preserves a sentinel record in the production SQLite database on the EBS volume.

Docker-socket functionality and required application AWS capabilities should be checked with focused smoke tests, but they do not need separate infrastructure acceptance machinery.

### Milestone 2: additional environments

After production automation is stable:

1. Add an explicit branch-to-environment mapping for the desired test branch.
2. Add its checked-in non-secret tfvars file.
3. Provision its runtime secret and S3 configuration.
4. Reuse the same environment Terraform root, workflow, scripts, and state-key pattern.
5. Confirm its resources, data, configuration, and concurrency are isolated from production.

Post-MVP work:

- protected environment destroy workflow
- automatic application rollback if a meaningful health signal is added
- richer monitoring and notifications
- automated AMI discovery/adoption if manual AMI updates prove insufficient

## Explicitly out of scope initially

- automatic latest-AMI adoption
- AWS Patch Manager
- automatic unattended reboots
- load balancers
- autoscaling
- multiple application instances
- zero-downtime or blue/green deployment
- automatic branch-deletion teardown
- SSH access
- generic arbitrary-branch environment naming
- commit-specific configuration snapshots
- automatic container rollback
- a new HTTP health service solely for infrastructure

## Files to inspect

The following files were examined during planning and are relevant implementation context.

### Current Rubber Duck deployment and build

- `.github/workflows/ci-cd.yml`
  - Current production-only build, ECR push, secret-file generation, and configuration upload workflow.
- `.github/scripts/build_docker.sh`
  - Current inline Dockerfile and image-tagging behavior.
- `.github/scripts/upload-file-s3.sh`
  - Current S3 upload helper.
- `aws/restart_duck.sh`
  - Current manual ECR login, image pull, container replacement, SQLite mount, Docker socket mount, and cleanup process.
  - Contains user work; inspect staged and unstaged changes before editing.
- `.gitignore`
  - Secret, environment, database, and scratch exclusions.
- `docs/deployment.md`
  - Existing partly outdated ECS-oriented deployment documentation.
- `README.md`
  - Project overview and deployment summary.
- `pyproject.toml`
- `poetry.lock`
  - Container dependency installation inputs.

### Application behavior relevant to deployment

- `src/main.py`
  - Reads `DISCORD_TOKEN` and `CONFIG_FILE_S3_PATH`.
- `src/gen_ai/gen_ai.py`
  - Reads `OPENAI_API_KEY`.
- `src/utils/config_loader.py`
  - Loads configuration from S3 using boto3.
- `src/utils/resource_staging.py`
  - Uses S3.
- `src/utils/python_exec_container.py`
  - Connects to the host Docker daemon and requires the Docker socket mount.
- `src/utils/send_email.py`
  - Review explicit AWS credential handling so the instance role works when keys are absent.
- `src/storage/sql_connection.py`
  - SQLite and other SQL connection behavior.
- `src/storage/sql_metrics.py`
- `src/storage/sql_quest.py`
- `src/metrics/reporter.py`
  - Database environment/configuration behavior.
- `src/armory/tool_cache.py`
  - SQL-backed cache behavior.
- `datasets/`
- `rubrics/`
  - Currently included in the application image.

### Autograder reference implementation

The reference deployment is outside this repository at:

`~/teach/cs301r-agentic/autograder/`

Important files:

- `~/teach/cs301r-agentic/autograder/deploy/README.md`
- `~/teach/cs301r-agentic/autograder/deploy/first-time-bootstrap.sh`
- `~/teach/cs301r-agentic/autograder/deploy/deploy.sh`
- `~/teach/cs301r-agentic/autograder/deploy/connect-to-instance.sh`
- `~/teach/cs301r-agentic/autograder/deploy/build_artifact.py`
- `~/teach/cs301r-agentic/autograder/deploy/scripts/instance-bootstrap.sh`
- `~/teach/cs301r-agentic/autograder/deploy/scripts/install-release.sh`
- `~/teach/cs301r-agentic/autograder/deploy/scripts/health-check.sh`
- `~/teach/cs301r-agentic/autograder/deploy/systemd/cs301r-autograder.service`
- `~/teach/cs301r-agentic/.github/workflows/autograder-deploy.yml`

Terraform reference files:

- `~/teach/cs301r-agentic/autograder/deploy/terraform/backend.tf`
- `~/teach/cs301r-agentic/autograder/deploy/terraform/providers.tf`
- `~/teach/cs301r-agentic/autograder/deploy/terraform/main.tf`
- `~/teach/cs301r-agentic/autograder/deploy/terraform/ec2.tf`
- `~/teach/cs301r-agentic/autograder/deploy/terraform/iam.tf`
- `~/teach/cs301r-agentic/autograder/deploy/terraform/s3.tf`
- `~/teach/cs301r-agentic/autograder/deploy/terraform/variables.tf`
- `~/teach/cs301r-agentic/autograder/deploy/terraform/outputs.tf`
- `~/teach/cs301r-agentic/autograder/deploy/terraform/environments/autograder.tfvars`

Reuse the autograder's operational patterns for bootstrap/import, OIDC, S3-native state locking, account validation, SSM polling, and failure output. Do not copy its Amazon Linux selection, artifact packaging, or broad GitHub deployment policy unchanged.

## External references

- Official Ubuntu AMIs on AWS and Canonical owner identity:
  <https://documentation.ubuntu.com/aws/aws-how-to/instances/launch-ubuntu-ec2-instance/>
- Ubuntu on AWS:
  <https://documentation.ubuntu.com/aws/>
- Ubuntu security updates:
  <https://documentation.ubuntu.com/security/security-updates/>
- AWS Systems Manager Patch Manager prerequisites, documenting why Patch Manager is not relied on for Ubuntu 26.04:
  <https://docs.aws.amazon.com/systems-manager/latest/userguide/patch-manager-prerequisites.html>

## Implementation cautions

- Never commit secret values, generated `.env` files, private configuration, database contents, or Terraform local state.
- Inspect existing AWS resources before creating anything with names that may already exist.
- Import enterprise-managed shared resources rather than attempting to replace them.
- Do not expose SSH or application ports for debugging; use SSM.
- Do not destroy the production EBS data volume during routine EC2 replacement.
- Do not use short commit SHAs for image traceability.
- Do not assume EC2 `running` means bootstrap is complete; wait for cloud-init and SSM readiness.
- Do not pass secret values through Terraform, user data, SSM command arguments, or GitHub logs.
- Quote SSM commands safely and keep secrets out of command-line parameters.
- Preserve environment isolation in state keys, IAM policies, secret paths, S3 paths, containers, and EBS volumes.
