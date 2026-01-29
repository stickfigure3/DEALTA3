#!/bin/bash
# DELTA3 Deployment Script

set -e

# Configuration
ENVIRONMENT=${1:-dev}
STACK_NAME="delta3-${ENVIRONMENT}"
REGION=${AWS_REGION:-us-east-1}

echo "=========================================="
echo "  DELTA3 Deployment - ${ENVIRONMENT}"
echo "=========================================="
echo ""

# Check for AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Install it first:"
    echo "   brew install awscli"
    exit 1
fi

# Check for SAM CLI
if ! command -v sam &> /dev/null; then
    echo "❌ AWS SAM CLI not found. Install it first:"
    echo "   brew install aws-sam-cli"
    exit 1
fi

# Check AWS credentials
echo "🔑 Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Run:"
    echo "   aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "   Account: ${ACCOUNT_ID}"
echo "   Region: ${REGION}"
echo ""

# Create Lambda layer for dependencies
echo "📦 Building Lambda dependencies..."
cd lambda

# Create requirements.txt for Lambda
cat > requirements.txt << EOF
google-genai>=1.0.0
boto3>=1.34.0
EOF

# Build with SAM
cd ..
sam build --template-file infrastructure/template.yaml

# Deploy
echo ""
echo "🚀 Deploying to AWS..."
sam deploy \
    --stack-name ${STACK_NAME} \
    --region ${REGION} \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides Environment=${ENVIRONMENT} \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset

# Get outputs
echo ""
echo "📋 Getting deployment outputs..."
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
    --output text)

FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
    --output text)

FRONTEND_URL=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue" \
    --output text)

# Update frontend API URL
echo ""
echo "🔧 Updating frontend configuration..."
sed -i.bak "s|https://api.delta3.ai|${API_ENDPOINT}|g" frontend/app.js
rm -f frontend/app.js.bak

# Deploy frontend
echo ""
echo "🌐 Deploying frontend..."
aws s3 sync frontend/ s3://${FRONTEND_BUCKET}/ --delete

# Restore frontend config (for local development)
git checkout frontend/app.js 2>/dev/null || true

echo ""
echo "=========================================="
echo "  ✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "🌐 Frontend URL: ${FRONTEND_URL}"
echo "🔌 API Endpoint: ${API_ENDPOINT}"
echo ""
echo "📱 Twilio Webhook (if using SMS):"
echo "   ${API_ENDPOINT}/twilio/webhook"
echo ""
echo "Next steps:"
echo "1. Visit ${FRONTEND_URL}"
echo "2. Create an account"
echo "3. Add your Gemini API key"
echo "4. Start coding!"
echo ""
