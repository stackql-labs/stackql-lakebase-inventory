/** AI service – wraps Anthropic API for streaming chat. */

import Anthropic from '@anthropic-ai/sdk';
import type { ChatMessage } from '../models/types.js';

const QUERY_SYSTEM_PROMPT = `You are a StackQL expert assistant. StackQL lets users query cloud provider APIs using SQL syntax.

Key rules:
- StackQL uses SELECT statements to read cloud resources. The table naming convention is: provider.service.resource
- Always include required WHERE clause parameters (e.g., region for AWS, project for GCP, subscriptionId for Azure)
- Format all SQL in a fenced \`\`\`sql code block
- Only generate SELECT queries (no INSERT/UPDATE/DELETE in query mode)
- Use standard SQL syntax (WHERE, GROUP BY, ORDER BY, JOIN, etc.)
- Available providers include: aws, google, azure, databricks, github, cloudflare, okta, and many more

Examples:
- AWS EC2 instances: SELECT instanceId, instanceType, state FROM aws.ec2.instances WHERE region = 'us-east-1'
- GCP VMs: SELECT name, status, machineType FROM google.compute.instances WHERE project = 'my-project' AND zone = 'us-central1-a'
- Azure VMs: SELECT name, properties FROM azure.compute.virtual_machines WHERE subscriptionId = '...' AND resourceGroupName = '...'`;

const RESULTS_SYSTEM_PROMPT = `You are a cloud infrastructure analyst. When presented with query results:

- Summarise what the data shows at a high level
- Flag notable findings: high resource counts, unusual states, potential cost or security concerns
- Suggest follow-up queries that could provide deeper insight
- Do NOT repeat the raw data verbatim – summarise and interpret
- Be concise and actionable`;

function getClient(): Anthropic {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error(
      'ANTHROPIC_API_KEY not set. Set it in .env for local dev, or configure it in app.yaml for production.'
    );
  }
  return new Anthropic({ apiKey });
}

/** Stream a chat response as an async generator of text chunks. */
export async function* streamChat(
  messages: ChatMessage[],
  mode: 'query' | 'results'
): AsyncGenerator<string> {
  const client = getClient();
  const systemPrompt = mode === 'query' ? QUERY_SYSTEM_PROMPT : RESULTS_SYSTEM_PROMPT;

  const stream = await client.messages.stream({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 4096,
    system: systemPrompt,
    messages: messages.map((m) => ({ role: m.role, content: m.content })),
  });

  for await (const event of stream) {
    if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
      yield event.delta.text;
    }
  }
}
