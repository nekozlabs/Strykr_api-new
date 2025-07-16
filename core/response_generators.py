"""
Response generators module.
Contains functions for generating streaming and regular AI responses.
"""

import asyncio
import logging
import time
from django.http import StreamingHttpResponse

from .api_utils import client


async def handle_streaming_response(messages):
    """
    Handle streaming response generation.
    
    Args:
        messages: List of message dicts for OpenAI API
        
    Returns:
        StreamingHttpResponse object
    """
    # Start timing
    start_time = time.time()
    
    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        stream=True,
    )

    # Track response metrics
    total_tokens = 0
    chunk_count = 0

    # Use proper async generator for streaming
    async def generate_async():
        nonlocal total_tokens, chunk_count
        try:
            # Add buffer to prevent connection issues
            chunk_buffer = []
            buffer_size = 5  # Send chunks in small batches
            
            # Use regular iteration for the OpenAI stream (it's synchronous)
            for chunk in completion:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    chunk_buffer.append(content)
                    chunk_count += 1
                    total_tokens += len(content.split())  # Rough token estimate
                    
                    # Send buffered chunks periodically
                    if len(chunk_buffer) >= buffer_size:
                        yield ''.join(chunk_buffer)
                        chunk_buffer = []
                    
                    # Add small delay to prevent overwhelming
                    await asyncio.sleep(0.01)
            
            # Send any remaining buffered content
            if chunk_buffer:
                yield ''.join(chunk_buffer)
                
        except Exception as e:
            logging.error(f"Error in streaming generator: {str(e)}")
            yield f"\n\n[Error: Stream interrupted - {str(e)}]"
        finally:
            # Log response timing and metrics
            response_time = time.time() - start_time
            logging.info(f"🚀 STREAMING RESPONSE METRICS:")
            logging.info(f"   ⏱️  Total Response Time: {response_time:.2f}s")
            logging.info(f"   📊 Total Chunks: {chunk_count}")
            logging.info(f"   🔢 Estimated Tokens: {total_tokens}")
            logging.info(f"   ⚡ Tokens/Second: {total_tokens/response_time:.1f}" if response_time > 0 else "   ⚡ Tokens/Second: N/A")
            
            # Ensure completion stream is properly closed
            if hasattr(completion, 'close'):
                completion.close()

    # Use the async generator with StreamingHttpResponse
    response = StreamingHttpResponse(
        generate_async(), 
        content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # Disable Nginx buffering
    response["Connection"] = "keep-alive"  # Keep connection alive
    response["X-Skip-Gzip"] = "true"  # Signal to skip gzip compression
    return response


async def handle_regular_response(messages):
    """
    Handle regular (non-streaming) response generation.
    
    Args:
        messages: List of message dicts for OpenAI API
        
    Returns:
        Dict containing the response
    """
    # Start timing
    start_time = time.time()
    
    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
    )

    response = completion.choices[0].message.content.strip()

    if "```markdown\n" in response:
        response = response.split("```markdown\n")[1].rsplit("```", 1)[0]

    # Calculate response metrics
    response_time = time.time() - start_time
    response_length = len(response)
    word_count = len(response.split())
    
    # Log response timing and metrics
    logging.info(f"🚀 REGULAR RESPONSE METRICS:")
    logging.info(f"   ⏱️  Total Response Time: {response_time:.2f}s")
    logging.info(f"   📏 Response Length: {response_length:,} characters")
    logging.info(f"   📝 Word Count: {word_count:,} words")
    logging.info(f"   ⚡ Words/Second: {word_count/response_time:.1f}" if response_time > 0 else "   ⚡ Words/Second: N/A")

    return {"response": response} 