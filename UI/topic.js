const fs = require('fs').promises;
const csv = require('csv-parse/sync');
const stringify = require('csv-stringify/sync');

const extractRisingQueries = (text) => {
  const risingStart = text.indexOf("Rising Related Queries:");
  const topStart = text.indexOf("Top Related Queries:");
  if (risingStart === -1 || topStart === -1) {
      return [];
  }
  const risingText = text.slice(risingStart + "Rising Related Queries:".length, topStart).trim();
  const topics = risingText.split(",").map(t => t.trim()).filter(t => t);
  
  // Remove subtopics: keep only most specific topics in their original order
  const final = [];
  for (const topic of topics) {
      if (!final.some(existing => 
          existing.toLowerCase().includes(topic.toLowerCase()) || 
          topic.toLowerCase().includes(existing.toLowerCase())
      )) {
          final.push(topic);
      }
  }
  return final;
};

const topicExists = async (topic, filePath) => {
  try {
      if (!await fs.access(filePath).then(() => true).catch(() => false)) {
          return false;
      }
      const data = await fs.readFile(filePath, { encoding: 'utf-8' });
      const lines = data.split('\n').slice(1); // Skip header
      return lines.some(line => {
          const [existingTopic] = line.split(',');
          return existingTopic && existingTopic.trim().toLowerCase() === topic.toLowerCase();
      });
  } catch (error) {
      console.error(`Error checking topic: ${error.message}`);
      return false;
  }
};

// Function to read the first topic with status=0 from trend.csv
async function readFirstTopicWithStatus0(filePath) {
  try {
    const fileContent = await fs.readFile(filePath, 'utf-8');
    const records = csv.parse(fileContent, { columns: true, skip_empty_lines: true });
    for (const row of records) {
      if (row.status === '0') {
        return row.topic;
      }
    }
    return null; // Return null if no topic with status=0 is found
  } catch (error) {
    console.error('Error reading CSV file:', error.message);
    throw new Error('Failed to read topics from CSV');
  }
}

// Function to update a topic's status to 1 in trend.csv
async function updateTopicStatus(filePath, topic) {
  try {
    const fileContent = await fs.readFile(filePath, 'utf-8');
    const records = csv.parse(fileContent, { columns: true, skip_empty_lines: true });
    let updated = false;

    // Update status for the matching topic
    for (const row of records) {
      if (row.topic.trim().toLowerCase() === topic.trim().toLowerCase()) {
        row.status = '1';
        updated = true;
      }
    }

    if (!updated) {
      console.warn(`Topic "${topic}" not found in CSV for status update`);
      return false;
    }

    // Write updated records back to the CSV file
    const csvContent = stringify.stringify(records, { header: true });
    await fs.writeFile(filePath, csvContent, 'utf-8');
    console.log(`Updated status for topic "${topic}" to 1`);
    return true;
  } catch (error) {
    console.error('Error updating CSV file:', error.message);
    throw new Error('Failed to update topic status in CSV');
  }
}

module.exports = { readFirstTopicWithStatus0, updateTopicStatus };