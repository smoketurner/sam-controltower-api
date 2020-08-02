# AWS SAM Control Tower API

AWS SAM project to provide a [Control Tower](https://aws.amazon.com/controltower/) API that exposes an HTTPS endpoint for creating new AWS accounts.

- `POST /v1/accounts` - create a new AWS account
- `GET /v1/accounts/{recordId}` - return the status of a previous account creation request

When creating a new account, you can also provide a callback URL to be notified when the account creation has completed.

## Features

After a new account has been successfully created, this application will do the following actions on the new account:

1. Deletes the [default VPC](https://docs.aws.amazon.com/vpc/latest/userguide/default-vpc.html) in all of the regions
2. Blocks [S3 public access](https://docs.aws.amazon.com/AmazonS3/latest/dev/access-control-block-public-access.html) on the account
3. Add a CloudWatch Logs resource policy for Route53 [query logging](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/query-logs.html)

## Installation

This project should be installed in your AWS root account where you have already created a Control Tower landing zone (see the [Getting Started with AWS Control Tower](https://docs.aws.amazon.com/controltower/latest/userguide/getting-started-with-control-tower.html) guide for more information).

```
make setup
make build
make deploy
```

## TODO

### New Account Creation

- Enroll the new member account in Security Hub to the master account

### One-Time Best Practices

- Configure the [Audit Account](https://docs.aws.amazon.com/controltower/latest/userguide/how-control-tower-works.html#what-is-audit) to be the [Security Hub](https://docs.aws.amazon.com/securityhub/latest/userguide/securityhub-accounts.html) master account
- Configure the [Audit Account](https://docs.aws.amazon.com/controltower/latest/userguide/how-control-tower-works.html#what-is-audit) to be the [GuardDuty](https://docs.aws.amazon.com/guardduty/latest/ug/guardduty_organizations.html) master account
- Delegate access from the Master Account to the [Audit Account](https://docs.aws.amazon.com/controltower/latest/userguide/how-control-tower-works.html#what-is-audit) and create an organizational [IAM access analyzer](https://docs.aws.amazon.com/IAM/latest/UserGuide/what-is-access-analyzer.html)
- Apply an organization [opt-out policy](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_ai-opt-out_syntax.html#ai-opt-out-policy-examples) for all AI services
- Create a new `Network` account with a TransitGateway
- Create a new `SharedServices` account to host an AWS Service Catalog portfolio shared to the organization
- Create a VPC product in the service catalog that will automatically attach to the transit gateway and to a private Route53 hosted zone in the account
- Apply an SCP policy to block common actions

## References

- https://aws.amazon.com/solutions/implementations/customizations-for-aws-control-tower/
- https://github.com/awslabs/aws-deployment-framework
