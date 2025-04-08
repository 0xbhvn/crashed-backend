# Precomputed Aggregation

## Planning Roadmap

### 1. **Aggregate Identification and Data Structures**

**Identify Analytics Aggregates:**

- **Intervals:**  
  Aggregates that count occurrences in time buckets (e.g., 10-minute intervals over the last 24 hours).  
- **Series:**  
  Aggregates capturing sequential patterns (for example, consecutive games below or above a threshold).  
- **Occurrences:**  
  Aggregates for counting the number of games that meet a specific condition (e.g., crash point ≥ X or floor exactly matching a value) across a defined sample (last N games or last N hours).  
- **Last Games:**  
  Aggregates that keep track of the most recent game (or set of games) for given thresholds.

**Define Redis Data Structures for Each:**

- **Simple Counters:**  
  Use Redis hashes (or individual keys) for each threshold. For example, key structure:

  ```text
  analytics:occurrences:min:<value>  => hash fields { count, total_games, first_game_time, last_game_time }
  ```

- **Time-Series Data (Intervals):**  
  Consider a sorted set or a hash mapping time bucket identifiers (or “bucket start” timestamps) to a serialized JSON object that includes the count and any relevant timestamps. For example:  

  ```text
  analytics:intervals:min:<value> => hash field with keys as “bucket_<timestamp>” and values as JSON { count, total_games }.
  ```

- **Sequential Patterns (Series):**  
  Store these as a list (or a single JSON object) keyed under:  

  ```text
  analytics:series:min:<value>
  ```  

  Contain a list of series objects (each object details start_game, end_game, length, and follow_streak data).
- **Last Games:**  
  Store a simple key per threshold with the most recent game details, for instance:  

  ```text
  analytics:last_game:min:<value>  => JSON representation
  ```

---

### 2. **Incremental Update Logic**

**Core Idea:**  
Perform incremental updates every time a new game is processed so that aggregates are updated exactly once per event. This prevents recalculation for every frontend call.

**Implementation Steps:**

1. **New Game Processing Callback:**  
   In your main game processing (likely in the BCCrashMonitor callback), add a call to an aggregation update service. For every new game:
   - Determine which aggregates (intervals, series, occurrences, last games) are affected based on the new game’s data.
   - For each analytic type, invoke the corresponding update logic.

2. **Implement Helper Functions:**  
   For each type:

   - **For Simple Counters (Occurrences):**
     - Read the current counter from Redis.
     - Increment the count if the new game meets the threshold.
     - Update the "total_games" counter and adjust timestamps accordingly.

   - **For Time-Series Data (Intervals):**
     - Map the new game’s timestamp to its interval bucket (e.g., round to the nearest 10 minutes).
     - Retrieve the existing bucket aggregate from Redis and update its count and total games.

   - **For Sequential Patterns (Series):**
     - Determine if the new game continues an existing series or ends it.
     - Update the corresponding series structure or push a new series object.

   - **For Last Games:**
     - Compare the new game with the current stored value (if any) and update if it’s more recent or meets the criteria.

3. **Atomicity:**  
   - **Transaction Support:**  
     Use Redis transactions (MULTI/EXEC) or Lua scripting if updating multiple keys that must be consistent. This way, the overall state will not be left partial if a failure occurs midway.

4. **Versioning:**  
   - Include a global version or timestamp in your cache keys (or as a separate key).  
   - Every time a new game is processed, increment (or update) this version. API endpoints will automatically retrieve keys with the updated version, ensuring they never see stale aggregates.

---

### 3. **Integrating with Existing Routes and Services**

**Modify Routes:**  

- In your existing analytics routes (in files like `intervals.py`, `series.py`, `occurrences.py`, `last_games.py`), change the computation logic to simply read the precomputed results from Redis.
- The routes should use the same key-generation logic (including versioning) so they can quickly return cached results with minimal processing.

**Fallback Handling:**  

- If a key is missing (cache miss), then your service should trigger a recomputation for that specific aggregate. However, ideally, this should be rare once the precomputation is in place.

**Redis Helper Functions:**  

- Create a set of utility functions that:
  - Generate cache keys (for each aggregate type) using a standardized schema.
  - Read and write values (with proper serialization/deserialization).
  - Handle transactions, e.g., using Lua scripts if updates span multiple keys.

---

### 4. **Testing & Validation**

1. **Unit Tests:**  
   - Write unit tests for each helper function that updates an aggregate.  
   - Verify that incremental updates match full recomputation from the database.

2. **Integration Tests:**  
   - Simulate a stream of new game events and assert that the Redis keys reflect the expected aggregates.
   - Test the API endpoints to ensure that the returned analytics match the expected precomputed values.

3. **Load Testing:**  
   - While initial load testing is done, simulate high traffic to verify that the precomputed aggregation and caching meet latency and throughput requirements.

4. **Multi-Instance Testing:**  
   - Test how multiple API instances perform with version-based cache invalidation. This involves simulating game events and verifying that all instances serve consistent, updated analytics.

---

### 5. **Deployment and Monitoring**

1. **Rollout Strategy:**  
   - Start with a phased rollout on non-critical analytics endpoints.
   - Monitor key metrics: cache hit rates, CPU load from Redis, and API response latency.

2. **Monitoring:**  
   - Set up dashboards (e.g., via Grafana) to watch Redis memory usage, hit/miss rates, and TTL behaviors.
   - Include logs for each critical Redis operation, especially the update operations on aggregates.

3. **Adjust TTLs & Versioning:**  
   - Based on observed usage, tune TTL values and cache versioning intervals if needed.
   - If live updates are too frequent, consider a debounce or batching mechanism in your update service.

---

## Summary Checklist for Precomputed Aggregation

- **Identify all required aggregates** (occurrences, intervals, series, last games).
- **Define Redis data structures** for each aggregate type.
- **Implement incremental update logic** in a centralized helper/service that:
  - Is invoked in the game processing callback.
  - Uses transactions (or Lua scripts) for atomic updates.
- **Integrate versioning into cache keys.**
- **Modify API routes** to simply fetch from Redis rather than compute on the fly.
- **Thoroughly test** all update logic, both unit and integration tests.
- **Simulate and validate multi-instance synchronization,** ensuring that version-based updates keep all instances consistent.
- **Monitor and tune** aggregate TTLs and update frequencies based on real-world usage.

---

By following this plan, you will be able to update analytics once per new game event, store the results in Redis, and serve real-time precomputed analytics to users with minimal computation per API request. This approach not only improves performance and reduces load on your database but also provides a robust, scalable solution for delivering real-time analytics.
