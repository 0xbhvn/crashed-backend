-- SQL query to delete games with IDs from 7932561 to 7933796
-- Run this query before attempting to re-verify these games

DELETE FROM public.crash_games
WHERE CAST(game_id AS INTEGER) >= 7932561 
AND CAST(game_id AS INTEGER) <= 7933796;

-- Verify the deletion (optional)
SELECT COUNT(*) 
FROM public.crash_games
WHERE CAST(game_id AS INTEGER) >= 7932561 
AND CAST(game_id AS INTEGER) <= 7933796; 