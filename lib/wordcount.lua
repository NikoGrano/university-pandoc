-- Variables to store counts
local words = 0

-- Count words in a string
function count_words(str)
    -- Convert to string if not already
    str = str or ""
    if type(str) ~= "string" then
        str = tostring(str)
    end
    
    -- Count words (sequences of non-space characters)
    local count = 0
    for word in str:gmatch("%S+") do
        count = count + 1
    end
    return count
end

-- Calculate reading time in minutes for legal text
function calculate_reading_time(word_count)
    local words_per_minute = 200  -- Adjusted reading speed for legal text
    local minutes = math.ceil(word_count / words_per_minute)
    return minutes
end

-- Process blocks of text
function Blocks (blocks)
    for _, block in ipairs(blocks) do
        if block.t == "Para" or block.t == "Plain" then
            local text = pandoc.utils.stringify(block)
            words = words + count_words(text)
        end
    end
end

-- Format number with space as thousand separator
function format_number(num)
    local formatted = tostring(num)
    local k
    while true do
        formatted, k = string.gsub(formatted, "^(-?%d+)(%d%d%d)", '%1 %2')
        if k == 0 then break end
    end
    return formatted
end

-- Return the final count and reading time
function Meta (meta)
    meta.wordcount = format_number(words)
    meta.readingtime = tostring(calculate_reading_time(words))
    return meta
end
