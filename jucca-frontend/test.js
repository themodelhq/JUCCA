const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();
    
    // Load the HTML file
    await page.goto(`file:///workspace/jucca-frontend/dist/index.html`);
    
    // Check if the page loaded correctly
    const title = await page.title();
    console.log('Page title:', title);
    
    // Check for key elements
    const logo = await page.$('.logo');
    const chatContainer = await page.$('.chat-container');
    const input = await page.$('#questionInput');
    
    console.log('Logo found:', !!logo);
    console.log('Chat container found:', !!chatContainer);
    console.log('Input field found:', !!input);
    
    // Test sending a message
    await page.fill('#questionInput', 'Can I sell Nike shoes?');
    await page.click('#sendBtn');
    
    // Wait for response
    await page.waitForTimeout(1500);
    
    // Check if response was added
    const messages = await page.$$('.message');
    console.log('Messages count:', messages.length);
    
    await browser.close();
    
    console.log('Test completed successfully!');
})();
