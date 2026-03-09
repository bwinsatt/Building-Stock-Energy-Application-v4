#!/bin/bash

echo "🚀 Setting up Partner Components Sample App"
echo "=========================================="

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Please run this script from the sample-app directory"
    exit 1
fi

# Check if the library is built
if [ ! -f "../../dist/p-components.es.js" ]; then
    echo "📦 Building Partner Components library..."
    cd ../..
    npm run build
    cd examples/sample-app
else
    echo "✅ Library already built"
fi

# Install dependencies
echo "📥 Installing dependencies..."
npm install

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the development server:"
echo "  npm run dev"
echo ""
echo "To build for production:"
echo "  npm run build"
echo ""
echo "To preview production build:"
echo "  npm run preview"
echo ""