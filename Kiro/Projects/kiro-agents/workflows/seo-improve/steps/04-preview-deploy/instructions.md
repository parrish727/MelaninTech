# Step: Preview Deploy

Deploy the changes to the preview environment for visual validation.

## Actions
1. Apply the code changes from step 03-generate-fix to the preview branch
2. Trigger a preview build via `gateway("docker.build_deploy", {"service": "preview-server"})`
3. Wait for the build to complete
4. Return the preview URL for the next step
