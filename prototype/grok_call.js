import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "$XAI_API_KEY",
  baseURL: "https://api.x.ai/v1",
});

const completion = await client.chat.completions.create({
  model: "grok-4",
  messages: [
    {
      role: "user",
      content: "What is the meaning of life, the universe, and everything?"
    }
  ]
});