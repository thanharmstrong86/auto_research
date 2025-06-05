const express = require('express');
const axios = require('axios');
const { readFirstTopicWithStatus0, updateTopicStatus } = require('./topic.js');
const app = express();
app.use(express.json());

const CSV_FILE_PATH = 'trend.csv';
const BASE_URL = 'http://127.0.0.1:2024';
let THREAD_ID = null;
const ASSISTANT_ID = '305372d9-87ef-5273-ae23-8d70a69e9f28';
let CHECKPOINT_ID = null;

// Function to extract checkpoint_id for task named "human_feedback"
function getCheckpointId(jsonData) {
  for (const item of jsonData) {
    if (item.tasks) {
      for (const task of item.tasks) {
        if (task.name === 'human_feedback') {
          if (item.checkpoint && item.checkpoint.checkpoint_id) {
            return item.checkpoint.checkpoint_id;
          }
        }
      }
    }
  }
  return null;
}

app.post('/process-trends', async (req, res) => {
  const { keyword } = req.body;
  if (!keyword) {
      return res.status(400).json({ error: 'Keyword is required' });
  }

  // Create assistant for trend detection
  // curl --location 'http://localhost:2024/assistants' \
  // --header 'Content-Type: application/json' \
  // --data '{
  //   "assistant_id": "",
  //   "graph_id": "google_trend_detection",
  //   "config": {},
  //   "metadata": {},
  //   "if_exists": "raise",
  //   "name": "",
  //   "description": null
  // }'

  try {
      // Call LangGraph Dev API to get trends data
      const response = await axios.post('http://localhost:2024/runs/stream', {
          assistant_id: '64128a4d-299b-5208-948c-5c7c46c0a50a',
          input: { messages: [{ role: 'human', content: keyword }] },
          stream_mode: ['values'],
      }, {
          headers: { 'Content-Type': 'application/json' }
      });

      // Assuming the last chunk contains the tool output
      const chunks = [];
      for await (const chunk of response.data) {
          chunks.push(chunk);
      }
      const rawResult = chunks[chunks.length - 1]?.data?.output || '';

      // Process trends data
      const risingTopics = extractRisingQueries(rawResult);
      const results = [];
      for (const topic of risingTopics) {
          const exists = await topicExists(topic, 'trend.csv');
          results.push({ topic, exists });
      }

      res.json({ risingTopics, results });
  } catch (error) {
      console.error(`Error processing trends: ${error.message}`);
      res.status(500).json({ error: 'Failed to process trends' });
  }
});

// Step 1: Webhook to receive chat message (mimics "When chat message received")
app.post('/auto-research', async (req, res) => {
  try {
    // Step 1: Read the first topic with status=0
    const topic = await readFirstTopicWithStatus0(CSV_FILE_PATH);
    if (!topic) {
      return res.status(400).json({ error: 'No topics with status=0 found in trend.csv' });
    }
    console.log('Selected topic:', topic);

    // Step 2: Create Thread (mimics "Create theard" node)
    const createThreadResponse = await axios.post(`${BASE_URL}/threads`, {}, {
      headers: { 'Content-Type': 'application/json' }
    });
    console.log('Thread created:', createThreadResponse.data);

    //Get the thread ID from the createThreadResponse
    THREAD_ID = createThreadResponse.data.thread_id;
    console.log('Thread ID:', THREAD_ID);
    console.log('Topic:', topic);

    // Step 3: Run Thread Plan (mimics "Run thread Plan" node)
    const runPlanBody = {
      input: { topic: topic },
      config: {
        configurable: {
          report_structure: `Use this structure to create a report on the user-provided topic:
1. Introduction (no research needed)
   - Brief overview of the topic area
2. Main Body Sections:
   - Each section should focus on a sub-topic of the user-provided topic
3. Conclusion
   - Aim for 1 structural element (either a list of table) that distills the main body sections
   - Provide a concise summary of the report`,
          search_api: 'tavily',
          search_api_config: null,
          number_of_queries: 2,
          max_search_depth: 2,
          planner_provider: 'google_genai',
          planner_model: 'gemini-2.0-flash',
          writer_provider: 'google_genai',
          writer_model: 'gemini-2.0-flash',
          supervisor_model: 'google_genai:gemini-2.0-flash',
          researcher_model: 'google_genai:gemini-2.0-flash',
          thread_id: THREAD_ID
        }
      },
      metadata: { from_studio: true, LANGGRAPH_API_URL: BASE_URL },
      stream_mode: ['debug', 'messages'],
      stream_subgraphs: true,
      assistant_id: ASSISTANT_ID,
      interrupt_before: [],
      interrupt_after: [],
      multitask_strategy: 'rollback',
      checkpoint_during: true
    };

    const runPlanResponse = await axios.post(`${BASE_URL}/threads/${THREAD_ID}/runs/stream`, runPlanBody, {
      headers: { 'Content-Type': 'application/json' }
    });
    console.log('-----------Run plan response:---------------');
    console.log(runPlanResponse.data);

    // Step 4: Fetch Thread History (to get the checking point ID for approve and run thread)
    const historyResponse = await axios.post(`${BASE_URL}/threads/${THREAD_ID}/history`, { limit: 1000 }, {
      headers: { 'Content-Type': 'application/json' }
    });
    //console.log('Thread history:', historyResponse.data);

    // Get checkpoint_id for "human_feedback" task
    CHECKPOINT_ID = getCheckpointId(historyResponse.data);
    if (!CHECKPOINT_ID) {
      throw new Error('checkpoint_id not found for task "human_feedback"');
    }
    console.log('Checkpoint ID:', CHECKPOINT_ID);

    // Step 5: Approve and Run Thread (mimics "Approve and Run thread" node)
    const approveRunBody = {
      command: { resume: true },
      config: { configurable: { thread_id: THREAD_ID } },
      metadata: { from_studio: false, LANGGRAPH_API_URL: BASE_URL },
      stream_mode: ['debug', 'messages'],
      stream_subgraphs: true,
      assistant_id: ASSISTANT_ID,
      interrupt_before: [],
      interrupt_after: [],
      checkpoint: { checkpoint_id: CHECKPOINT_ID, thread_id: THREAD_ID, checkpoint_ns: '' },
      multitask_strategy: 'rollback',
      checkpoint_during: true
    };

    const approveRunResponse = await axios.post(`${BASE_URL}/threads/${THREAD_ID}/runs/stream`, approveRunBody, {
      headers: { 'Content-Type': 'application/json' }
    });
    console.log('-------------Approve and run response:------------------');
    console.log(approveRunResponse.data);

    // Step 6: Fetch Thread info
    const threadResponse = await axios.get(`${BASE_URL}/threads/${THREAD_ID}`, {
      headers: { 'Content-Type': 'application/json' }
    });
    console.log('Thread info:', threadResponse.data);

    // Step 7: Update topic status to 1
    await updateTopicStatus(CSV_FILE_PATH, topic);
    console.log(`Status updated for topic "${topic}" to 1`);

    // Respond to the webhook
    res.json({ status: 'Workflow completed', data: threadResponse.data.values.final_report });
  } catch (error) {
    console.error('Error:', error.message);
    res.status(500).json({ error: 'Workflow failed', details: error.message });
  }
});

// Start the server
const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});