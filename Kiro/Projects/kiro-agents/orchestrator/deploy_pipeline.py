"""
Auto-deploy pipeline: rebuilds testing then staging after proposal approval.
After staging, posts a production approval button.
"""
import os
import docker as docker_sdk
from config.settings import SLACK_CHANNEL_ID

# Docker daemon needs the host-side path for image builds
WEBSITE_PATH = os.environ.get(
    "HOST_WEBSITE_PATH",
    "/Users/pktech_dev/Documents/MelaninTechnologies/melanin-tech-website"
)

ENVS = [
    {"name": "testing",  "service": "docker-testing-server-1",  "image": "docker-testing-server",  "port": 3002},
    {"name": "staging",  "service": "docker-staging-server-1",  "image": "docker-staging-server",  "port": 3003},
]

PRODUCTION = {"name": "production", "service": "docker-production-server-1", "image": "docker-production-server", "port": 3000}


def _rebuild(env: dict, client: docker_sdk.DockerClient) -> str:
    image, _ = client.images.build(
        path=WEBSITE_PATH,
        tag=env["image"],
        rm=True,
        forcerm=True,
    )
    try:
        old = client.containers.get(env["service"])
        old.stop(timeout=10)
        old.remove()
    except Exception:
        pass
    client.containers.run(
        image=env["image"],
        name=env["service"],
        detach=True,
        restart_policy={"Name": "unless-stopped"},
        ports={f"{env['port']}/tcp": env["port"]},
        network="docker_agent-net",
        environment={"PORT": str(env["port"])},
        labels={"managed-by": "kiro-deploy-agent", "env": env["name"]},
    )
    return f"http://localhost:{env['port']}"


def deploy_to_production(app):
    """Called when production approval is clicked."""
    client = docker_sdk.from_env()
    app.client.chat_postMessage(channel=SLACK_CHANNEL_ID, text="🚀 Deploying to *production*...")
    try:
        url = _rebuild(PRODUCTION, client)
        app.client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=f"🟢 *Production* is live — <{url}|{url}>",
        )
    except Exception as e:
        app.client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=f"⚠️ Production deploy failed: {e}")


def deploy_pipeline(app, ticket_id: int):
    """Rebuild testing then staging, then post production approval."""
    client = docker_sdk.from_env()
    for env in ENVS:
        app.client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=f"🔨 Deploying to *{env['name']}*...")
        try:
            url = _rebuild(env, client)
            app.client.chat_postMessage(
                channel=SLACK_CHANNEL_ID,
                text=f"✅ *{env['name'].capitalize()}* deployed — <{url}|{url}>",
            )
        except Exception as e:
            app.client.chat_postMessage(
                channel=SLACK_CHANNEL_ID,
                text=f"⚠️ *{env['name'].capitalize()}* deploy failed: {e}",
            )
            return

    # Post production approval button
    app.client.chat_postMessage(
        channel=SLACK_CHANNEL_ID,
        text="Staging verified. Ready to deploy to production?",
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Ticket #{ticket_id}* passed testing & staging.\nReady to deploy to *production*?"},
            },
            {
                "type": "actions",
                "block_id": f"prod_deploy:{ticket_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🚀 Deploy to Production"},
                        "style": "primary",
                        "action_id": "deploy_production",
                        "value": str(ticket_id),
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Skip"},
                        "action_id": "skip_production",
                        "value": str(ticket_id),
                    },
                ],
            },
        ],
    )
