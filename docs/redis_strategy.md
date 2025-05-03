# Redis Strategy & Real-Time Analytics Documentation

## Overview

The Crash Monitor backend is responsible for both real-time game processing and serving analytics endpoints. Given the frequency of incoming game events and the computational cost of the analytics queries, we want to leverage Redis in two complementary ways:

1. **Response Caching:**  
   Cache the responses for endpoints so that repeated frontend calls do not hit the database repeatedly.

2. **Real-Time Aggregation:**  
   Every time a new game comes in, update all analytics aggregates in Redis just once per game. Then, analytics endpoints will simply return these precomputed aggregates.

This document details the combined strategy for both caching and real‑time updates.

---

## 1. Real-Time Aggregation & Precomputation

### Event-Driven Updates

- **New Game Callback:**  
  When a new game is received (e.g., via the crash monitor's callback), immediately compute or update all necessary analytics aggregates. These computations include:
  - Occurrence counts (e.g., games with crash point ≥ a threshold)
  - Interval-based aggregations (e.g., occurrences in 10-minute buckets)
  - Series analysis (consecutive games without meeting a threshold)

- **Single Update per Game:**  
  The heavy analytics calculations are performed only once per new game event. Once computed, the results are stored in Redis under dedicated keys so that subsequent API calls retrieve the precomputed results.

- **Incremental Computation:**  
  Where possible, update aggregates incrementally:
  - **Counts & Occurrences:** Increment counters based on the new game's values.
  - **Intervals & Series:** Recalculate only the affected intervals or series.
  - This minimizes the processing overhead on each new game event.

### Background Precomputation (Optional)

- **Scheduled Jobs:**  
  For extremely heavy queries or if an event-driven update is not feasible, consider running scheduled background jobs that update aggregates at fixed intervals. However, the preferred approach is to update immediately upon each game event.

---

## 2. Response Caching Strategy

### Games Endpoints

- **Short TTL Caching:**  
  Since game data is updated in real time, cache game list and detail responses with a short time-to-live (TTL) of approximately 10–30 seconds.  
  **Key Example:**  
  `games:list:page:1:per_page:10:tz:America/New_York:<version>`

- **Usage:**  
  When a frontend request comes in, first check Redis for a cached response. If the key exists and is fresh, return it; otherwise, fetch from the database and update the cache.

### Analytics Endpoints

- **Longer TTL / Persistent Storage:**  
  Analytics endpoints are more computationally expensive. Once a new game updates the analytics aggregates, store these results in Redis with either no TTL (if updates occur with every game) or a longer TTL (e.g., 60–120 seconds) if slight staleness is acceptable.  
  **Key Example:**  
  `analytics:interval:min:10:interval:10:hours:24:<version>`

- **Usage:**  
  API calls simply read the precomputed results from Redis rather than recalculating aggregates from scratch.

---

## 3. Cache Invalidation & Versioning

### Versioning Strategy

- **Cache Version or Timestamp:**  
  Incorporate a "cache version" or timestamp in all Redis keys. This version is updated (incremented or changed) every time a new game is processed.
  
- **How It Works:**  
  - All analytics keys include the version (or "last updated" timestamp).
  - On a new game event, update the version.
  - API calls always read data based on the latest version. This avoids stale data being returned to users.

### Event-Based Invalidation

- **Pub/Sub for Invalidation:**  
  For multiple API instances, use Redis Pub/Sub channels to broadcast cache invalidation events. When one instance updates analytics, all instances update their local cache or reference the new version.

- **Fallback:**  
  In case of a cache miss or if Redis is unavailable, the system should fall back to querying the database and then updating Redis.

---

## 4. Distributed Consistency & Scalability

### Pub/Sub & Distributed Updates

- **Centralized Analytics Updates:**  
  When a new game is processed, a background worker (or the callback itself) updates the aggregates in Redis and publishes an update on a specific Pub/Sub channel (e.g., `analytics_updates`).

- **API Server Subscription:**  
  All API servers subscribe to the channel. When an update is published, they refresh their cached analytics results accordingly. This ensures that all instances serve consistent and up-to-date data.

### Rate Limiting

- **Protecting Analytics Endpoints:**  
  Implement Redis-based rate limiting for analytics endpoints to prevent overload. This helps protect expensive queries and ensures that even in high-traffic scenarios, the load is managed effectively.

---

## 5. Implementation Considerations

### Key Naming Conventions

- **Games Endpoint Keys:**  
  Use descriptive key names that encode pagination, sorting, timezone, and cache version.  
  **Example:**  
  `games:list:page:1:per_page:10:tz:America/New_York:<version>`

- **Analytics Keys:**  
  Similarly, include all relevant query parameters in the key along with the cache version.  
  **Example:**  
  `analytics:interval:min:10:interval:10:hours:24:<version>`

### Update Flow

1. **New Game Event:**
   - The new game is processed.
   - Analytics aggregates are computed (incrementally or from scratch).
   - Redis keys are updated with new aggregate values along with an updated version.
   - Optionally, a Pub/Sub event is published to inform all API nodes of the change.

2. **Frontend Request:**
   - The API endpoint checks Redis for a matching key (including the version).
   - If found, the precomputed result is returned immediately.
   - If not, the backend either recomputes the aggregate or returns a fallback, then updates Redis.

### TTL Tuning

- **Games Data:**  
  Use a TTL of 10–30 seconds.
- **Analytics Data:**  
  Use a TTL of 60–120 seconds or rely on versioning and event updates for near‑immediate refresh.

### Error Handling

- **Fallback Strategy:**  
  If Redis is down or a key is missing, the backend should fetch the required data from the database, update Redis, and then return the response.
- **Graceful Degradation:**  
  Ensure that the API remains responsive even if cache invalidation or Redis operations fail.

---

## 6. Summary & Next Steps

### Summary

- **Real-Time Updates:**  
  Compute analytics aggregates immediately on each new game event. Use Redis to store these aggregates so that each API call simply returns precomputed data.
- **Response Caching:**  
  Cache both games and analytics endpoints in Redis with appropriate TTLs. Games endpoints use short TTLs while analytics endpoints use longer TTLs (or versioning) to prevent heavy recalculations.
- **Cache Invalidation:**  
  Implement a cache versioning system (or use Pub/Sub) to invalidate and update caches across multiple API instances.
- **Distributed Consistency:**  
  Ensure all API nodes stay in sync using Redis Pub/Sub for updates and consider rate limiting to control access to heavy analytics endpoints.

### Next Steps

1. **Implementation:**  
   - Update the game callback to trigger incremental analytics updates in Redis.
   - Develop helper functions for computing and storing aggregates in Redis.
   - Integrate Redis Pub/Sub to distribute cache invalidation events across all API instances.

2. **Testing:**  
   - Verify that new game events update analytics exactly once.
   - Test cache keys for both games and analytics endpoints for correctness and performance.
   - Simulate distributed scenarios to ensure consistency across multiple API nodes.

3. **Monitoring & Tuning:**  
   - Monitor cache hit rates and latency for both endpoints.
   - Adjust TTLs and versioning parameters based on real-world traffic.
   - Evaluate rate limiting on heavy endpoints to prevent abuse.

By following this combined strategy, the backend team can ensure that real-time analytics are both efficient and scalable, providing users with up-to-date insights without incurring unnecessary computational overhead on every request.

---

## 7. Implementation Checklist

### Setup and Configuration

- [x] Set up Redis instance with appropriate memory allocation
- [x] Configure Redis persistence (RDB/AOF) based on data importance
- [x] Implement Redis connection pooling in the application
- [x] Create helper functions for standardized Redis key generation
- [x] Set up error handling and fallback mechanisms for Redis failures

### Response Caching Implementation

- [x] Implement middleware or decorator for caching API responses
- [x] Create caching logic for games endpoints with short TTL (10-30s)
- [x] Implement caching for analytics endpoints with appropriate TTL or versioning
- [x] Add cache miss handling with database fallback
- [x] Configure response serialization/deserialization (JSON/Protobuf)

### Real-Time Aggregation Implementation

- [ ] Identify all required analytics aggregates to be precomputed
- [ ] Create data structures for each aggregate type (counters, lists, sorted sets, etc.)
- [ ] Implement game processing callback that triggers Redis updates
- [ ] Develop incremental update logic for each aggregate type:
  - [ ] Simple counters (e.g., games above thresholds)
  - [ ] Time-series data (e.g., 10-minute interval buckets)
  - [ ] Sequential patterns (e.g., consecutive games analysis)
- [ ] Add transaction support for updating multiple related analytics keys atomically

### Versioning and Invalidation System

- [x] Implement a global version key or timestamp in Redis
- [x] Create logic to increment/update version on new game events
- [x] Modify cache key generation to include version information
- [-] Implement Pub/Sub channels for distributing cache invalidation events (Note: Version-based invalidation implemented instead)
- [-] Add logic in API servers to subscribe to invalidation events (Note: Using version-based approach instead of Pub/Sub)

### Distributed Consistency

- [-] Set up Pub/Sub channels for analytics updates (Note: Version-based invalidation used instead of Pub/Sub)
- [-] Implement publisher logic in game processing service (Note: Using direct cache invalidation with version)
- [-] Add subscriber logic in API servers to refresh caches (Note: Not needed with version-based approach)
- [ ] Test multi-instance synchronization with simulated game events
- [ ] Implement Redis-based rate limiting for heavy analytics endpoints

### Testing and Validation

- [x] Create unit tests for each Redis operation (set, get, increment, etc.)
- [x] Develop integration tests for the complete caching flow
- [-] Implement load tests to validate performance under high traffic (Note: Basic performance validation done)
- [x] Test cache invalidation and versioning mechanisms
- [x] Test fallback mechanisms when Redis is unavailable

### Monitoring and Optimization

- [-] Set up Redis monitoring (memory usage, hit rate, etc.) (Note: Basic monitoring in place)
- [-] Add instrumentation for tracking cache hit/miss rates (Note: Simple tracking implemented)
- [x] Implement logging for critical Redis operations
- [ ] Create dashboards for cache performance metrics
- [-] Develop automation for TTL tuning based on usage patterns (Note: Manual tiered TTL implemented)

### Documentation and Knowledge Sharing

- [x] Update API documentation to reflect caching behavior
- [x] Document Redis key schema and data structures
- [x] Create runbooks for common Redis operational tasks
- [x] Document failure scenarios and recovery procedures
- [x] Prepare knowledge-sharing sessions for the team

### Rollout Strategy

- [x] Plan phased implementation starting with non-critical endpoints
- [x] Identify metrics to validate improvements (latency, DB load, etc.)
- [x] Create rollback plan in case of unexpected issues
- [x] Schedule gradual rollout to production with monitoring
- [x] Establish criteria for successful implementation
