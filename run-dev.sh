#!/bin/bash
# Development server with hot reload and full functionality

echo "🚀 Crash Monitor Development Server"
echo "=================================="
echo ""

# Check for virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    echo "✓ Virtual environment already activated: $VIRTUAL_ENV"
else
    # Try to find and activate virtual environment
    VENV_ACTIVATED=false
    for venv_dir in venv .venv env; do
        if [ -d "$venv_dir" ]; then
            echo "Activating virtual environment: $venv_dir"
            source "$venv_dir/bin/activate"
            VENV_ACTIVATED=true
            break
        fi
    done
    
    if [ "$VENV_ACTIVATED" = false ]; then
        echo "⚠️  Warning: No virtual environment found or activated!"
        echo "   Looked for: venv, .venv, env"
        echo "   Consider creating one with: python3 -m venv venv"
        echo ""
        read -p "Continue without virtual environment? (y/N) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Exiting..."
            exit 1
        fi
    fi
fi

echo ""

# Check if aiohttp-devtools is installed
if ! python3 -c "import aiohttp_devtools" 2>/dev/null; then
    echo "❌ Error: aiohttp-devtools is not installed!"
    echo "   Please install it with: pip install aiohttp-devtools"
    exit 1
fi

# Set development environment
export ENVIRONMENT=development

# Parse command line arguments
SKIP_CATCHUP="true"  # Default to true for faster development startup
VERBOSE=""
PORT=${API_PORT:-8000}

while [[ $# -gt 0 ]]; do
    case $1 in
        --run-catchup)
            SKIP_CATCHUP="false"  # Explicitly enable catchup if needed
            shift
            ;;
        --verbose)
            VERBOSE="--verbose"
            shift
            ;;
        --port)
            if [[ -z "$2" || "$2" =~ ^-- ]]; then
                echo "Error: --port requires a numeric argument"
                echo "Usage: $0 [--run-catchup] [--verbose] [--port PORT]"
                exit 1
            fi
            if ! [[ "$2" =~ ^[0-9]+$ ]]; then
                echo "Error: Port must be a number, got: $2"
                exit 1
            fi
            PORT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--run-catchup] [--verbose] [--port PORT]"
            exit 1
            ;;
    esac
done

# Export skip catchup preference for the Python module
export SKIP_CATCHUP=$SKIP_CATCHUP

echo "Configuration:"
echo "  Port: $PORT"
echo "  Skip catchup: $SKIP_CATCHUP"
echo "  Verbose: ${VERBOSE:-No}"
echo "  Environment: ${ENVIRONMENT:-development}"
echo ""
echo "The server will automatically restart when you modify any Python file."
echo "Press Ctrl+C to stop."
echo ""

# Run the development server using adev
adev runserver --app-factory create_app --port $PORT $VERBOSE dev_server.py
