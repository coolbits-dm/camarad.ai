import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { planId, workspace, selectedAgentPresetIds, preferences } = req.body;

    // TODO: Real implementation:
    // 1. Create/update user record
    // 2. Create workspace
    // 3. Instantiate agents (UserAgent records)
    // 4. Set planId + trialEndsAt (15 days from now)
    // 5. Initialize preferences
    // 6. Create Stripe checkout session for trial activation

    // Mock response
    const mockResponse = {
      success: true,
      userId: 'user-001',
      workspaceId: 'ws-001',
      agentIds: selectedAgentPresetIds.map((_: string, i: number) => `agent-${i + 1}`),
      trialEndsAt: new Date(Date.now() + 15 * 24 * 60 * 60 * 1000).toISOString(),
      redirectUrl: `/p/${workspace.type}`,
    };

    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 500));

    return res.status(200).json(mockResponse);
  } catch (error) {
    console.error('Onboarding complete error:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
