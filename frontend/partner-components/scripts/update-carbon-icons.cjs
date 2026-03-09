#!/usr/bin/env node

/**
 * Update Carbon Icons JSON
 * 
 * Downloads the latest Carbon icons data from Iconify API
 * and updates the local carbon-icons.json file.
 * 
 * Usage:
 *   node scripts/update-carbon-icons.cjs
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

const API_URL = 'https://api.iconify.design/collection?prefix=carbon';
const OUTPUT_FILE = path.join(__dirname, '../src/components/PIcon/carbon-icons.json');

function fetchCarbonIcons() {
  return new Promise((resolve, reject) => {
    https.get(API_URL, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error(`Failed to fetch: ${res.statusCode}`));
        return;
      }

      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json);
        } catch (error) {
          reject(new Error(`Failed to parse JSON: ${error.message}`));
        }
      });
    }).on('error', (error) => {
      reject(error);
    });
  });
}

async function updateCarbonIcons() {
  try {
    console.log('📥 Fetching Carbon icon names json file from Iconify API...');
    const data = await fetchCarbonIcons();
    
    console.log('💾 Writing to carbon-icons.json...');
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(data, null), 'utf8');
    
    const iconCount = Object.values(data.categories || {}).flat().length + (data.hidden || []).length;
    console.log(`✅ Success! Updated carbon-icons.json with ${iconCount} icons.`);
  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  }
}

updateCarbonIcons();