-- Variables to store counts
local words = 0
local lisatiedot_words = 0
local in_lisatiedot = false

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
    
    -- Add to appropriate counter
    if in_lisatiedot then
        lisatiedot_words = lisatiedot_words + count
        return 0
    end
    return count
end

-- Calculate reading time in minutes for legal text
function calculate_reading_time(word_count)
    -- Avg adult reading speed is 161 words per minute for Finnish
    local words_per_minute = 150  -- Adjusted reading speed for legal text
    local minutes = math.ceil(word_count / words_per_minute)
    return minutes
end

-- Process metadata to track lisatiedot field
function Meta (meta)
    if meta.lisatiedot then
        in_lisatiedot = true
        local content = pandoc.utils.stringify(meta.lisatiedot)
        count_words(content)  -- This will add to lisatiedot_words
        in_lisatiedot = false
    end
    
    -- Set metadata values after processing, excluding lisatiedot words
    meta.wordcount = format_number(words - lisatiedot_words)
    meta.readingtime = tostring(calculate_reading_time(words - lisatiedot_words))
    return meta
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

