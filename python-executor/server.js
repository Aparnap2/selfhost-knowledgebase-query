import http from 'http';
import fs from 'fs';
import path from 'path';
import { exec, spawn } from 'child_process';
import { v4 as uuidv4 } from 'uuid';

// Enable debug mode
const isDebug = process.env.DEBUG === 'true';

// Log startup information
console.log('Starting Python executor service...');
console.log(`Debug mode: ${isDebug ? 'enabled' : 'disabled'}`);
console.log(`Node environment: ${process.env.NODE_ENV || 'not set'}`);

// Create directories for outputs
const tmpDir = path.join(process.cwd(), 'tmp');
const plotsDir = path.join(process.cwd(), 'plots');
const sessionsDir = path.join(process.cwd(), 'sessions');

[tmpDir, plotsDir, sessionsDir].forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
});

// Track active sessions
const sessions = new Map();

// Clean up any old session files
fs.readdir(sessionsDir, (err, files) => {
  if (err) {
    console.error(`Error reading sessions directory: ${err.message}`);
    return;
  }
  
  files.forEach(file => {
    const filePath = path.join(sessionsDir, file);
    fs.unlink(filePath, err => {
      if (err) console.error(`Error deleting old session file ${filePath}: ${err.message}`);
    });
  });
});

// Enhanced function to execute Python code with support for plots and sessions
async function executePython(code, sessionId = null, timeout = 30000) {
  // Generate a unique ID for this execution
  const executionId = uuidv4();
  const tempFile = path.join(tmpDir, `code_${executionId}.py`);
  const plotFile = path.join(plotsDir, `plot_${executionId}.png`);
  
  // Add plot saving code if matplotlib is detected
  let modifiedCode = code;
  if (code.includes('matplotlib') || code.includes('plt.')) {
    modifiedCode = `
${code}

# Save plot if one was created
import matplotlib.pyplot as plt
import os
if plt.get_fignums():
    plt.savefig('${plotFile.replace(/\\/g, '\\\\')}')
    print(f"\n[PLOT_SAVED]${plotFile.replace(/\\/g, '\\\\')}[/PLOT_SAVED]")
    plt.close()
`;
  }
  
  // If a session ID is provided, use the session file
  if (sessionId && sessions.has(sessionId)) {
    const sessionFile = path.join(sessionsDir, `session_${sessionId}.py`);
    
    // Read existing session code
    let sessionCode = fs.readFileSync(sessionFile, 'utf8');
    
    // Append new code
    sessionCode += `\n\n# New code - ${new Date().toISOString()}\n${modifiedCode}`;
    
    // Write updated session code
    fs.writeFileSync(sessionFile, sessionCode);
    
    // Use the session file for execution
    modifiedCode = sessionCode;
    fs.writeFileSync(tempFile, modifiedCode);
  } else {
    // Create a new file with the code
    fs.writeFileSync(tempFile, modifiedCode);
    
    // If a session ID was provided but doesn't exist, create it
    if (sessionId) {
      const sessionFile = path.join(sessionsDir, `session_${sessionId}.py`);
      fs.writeFileSync(sessionFile, modifiedCode);
      sessions.set(sessionId, { created: new Date() });
    }
  }
  
  console.log(`Executing Python code in ${tempFile}${sessionId ? ` (Session: ${sessionId})` : ''}`);
  
  return new Promise((resolve) => {
    // Execute the Python code with a timeout
    const pythonProcess = spawn('python', [tempFile]);
    
    let stdout = '';
    let stderr = '';
    let plotPath = null;
    
    // Set a timeout
    const timeoutId = setTimeout(() => {
      pythonProcess.kill();
      stderr += '\nExecution timed out after ' + (timeout / 1000) + ' seconds.';
      cleanup();
    }, timeout);
    
    // Collect stdout
    pythonProcess.stdout.on('data', (data) => {
      const output = data.toString();
      stdout += output;
      
      // Check for plot path in output
      const plotMatch = output.match(/\[PLOT_SAVED\](.+?)\[\/PLOT_SAVED\]/s);
      if (plotMatch) {
        plotPath = plotMatch[1];
        // Remove the marker from the output
        stdout = stdout.replace(/\[PLOT_SAVED\].+?\[\/PLOT_SAVED\]/s, '');
      }
    });
    
    // Collect stderr
    pythonProcess.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    // Handle process completion
    pythonProcess.on('close', (code) => {
      clearTimeout(timeoutId);
      cleanup();
    });
    
    // Clean up function
    function cleanup() {
      try {
        // Clean up the temporary file
        fs.unlinkSync(tempFile);
      } catch (err) {
        console.error(`Error cleaning up temp file: ${err.message}`);
      }
      
      // Check if a plot was generated
      let plotData = null;
      if (plotPath && fs.existsSync(plotPath)) {
        try {
          // Read the plot file as base64
          const plotBuffer = fs.readFileSync(plotPath);
          plotData = `data:image/png;base64,${plotBuffer.toString('base64')}`;
          
          // Clean up the plot file
          fs.unlinkSync(plotPath);
        } catch (err) {
          console.error(`Error processing plot file: ${err.message}`);
        }
      }
      
      // Return the result
      resolve({
        success: !stderr,
        code: modifiedCode,
        output: stdout,
        error: stderr,
        plot: plotData,
        sessionId: sessionId || null
      });
    }
  });
}

// Function to create a new session
function createSession() {
  const sessionId = uuidv4();
  const sessionFile = path.join(sessionsDir, `session_${sessionId}.py`);
  
  // Create an empty session file
  fs.writeFileSync(sessionFile, '# Python session created ' + new Date().toISOString() + '\n');
  
  // Track the session
  sessions.set(sessionId, { created: new Date() });
  
  return sessionId;
}

// Function to get session info
function getSession(sessionId) {
  if (!sessions.has(sessionId)) {
    return null;
  }
  
  const sessionFile = path.join(sessionsDir, `session_${sessionId}.py`);
  if (!fs.existsSync(sessionFile)) {
    sessions.delete(sessionId);
    return null;
  }
  
  const code = fs.readFileSync(sessionFile, 'utf8');
  return {
    id: sessionId,
    created: sessions.get(sessionId).created,
    code
  };
}

// Function to delete a session
function deleteSession(sessionId) {
  if (!sessions.has(sessionId)) {
    return false;
  }
  
  const sessionFile = path.join(sessionsDir, `session_${sessionId}.py`);
  if (fs.existsSync(sessionFile)) {
    fs.unlinkSync(sessionFile);
  }
  
  sessions.delete(sessionId);
  return true;
}

// Create a simple HTTP server
const server = http.createServer(async (req, res) => {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  // Handle preflight requests
  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }
  
  // Health check endpoint
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'healthy' }));
    return;
  }
  
  // Create a new session
  if (req.method === 'POST' && req.url === '/session') {
    try {
      const sessionId = createSession();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ 
        success: true, 
        sessionId,
        message: 'Session created successfully'
      }));
    } catch (error) {
      console.error('Error creating session:', error);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ 
        success: false, 
        error: error.message 
      }));
    }
    return;
  }
  
  // Get session info
  if (req.method === 'GET' && req.url.startsWith('/session/')) {
    try {
      const sessionId = req.url.split('/')[2];
      const session = getSession(sessionId);
      
      if (!session) {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ 
          success: false, 
          error: 'Session not found' 
        }));
        return;
      }
      
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ 
        success: true, 
        session 
      }));
    } catch (error) {
      console.error('Error getting session:', error);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ 
        success: false, 
        error: error.message 
      }));
    }
    return;
  }
  
  // Delete session
  if (req.method === 'DELETE' && req.url.startsWith('/session/')) {
    try {
      const sessionId = req.url.split('/')[2];
      const deleted = deleteSession(sessionId);
      
      if (!deleted) {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ 
          success: false, 
          error: 'Session not found' 
        }));
        return;
      }
      
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ 
        success: true, 
        message: 'Session deleted successfully' 
      }));
    } catch (error) {
      console.error('Error deleting session:', error);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ 
        success: false, 
        error: error.message 
      }));
    }
    return;
  }
  
  // Execute Python code endpoint
  if (req.method === 'POST' && req.url === '/execute') {
    let body = '';
    
    req.on('data', chunk => {
      body += chunk.toString();
    });
    
    req.on('end', async () => {
      try {
        const data = JSON.parse(body);
        const code = data.code || 'print("No code provided")';
        const sessionId = data.sessionId || null;
        const timeout = data.timeout || 30000; // Default 30 seconds
        
        console.log(`Executing Python code${sessionId ? ` in session ${sessionId}` : ''}`);
        
        const result = await executePython(code, sessionId, timeout);
        
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(result));
      } catch (error) {
        console.error('Error processing request:', error);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ 
          success: false, 
          error: error.message 
        }));
      }
    });
    return;
  }
  
  // Default response for unknown endpoints
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found' }));
});

// Start the server
const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});