-- ArtClaw Bridge startup script for 3ds Max
-- This MaxScript file triggers the Python startup script
-- Place in: %LOCALAPPDATA%/Autodesk/3dsMax/{version}/scripts/startup/ 
--        or: "Additional Startup Scripts" directory

(
    local pyStartup = (getDir #userStartupScripts) + "\\artclaw_startup.py"
    
    -- Try Additional Startup Scripts dir first
    if not (doesFileExist pyStartup) then (
        local additionalDir = (getDir #userScripts)
        if additionalDir != undefined then (
            pyStartup = additionalDir + "\\startup\\artclaw_startup.py"
        )
    )
    
    -- Also check next to this .ms file
    if not (doesFileExist pyStartup) then (
        local thisDir = getFilenamePath (getSourceFileName())
        pyStartup = thisDir + "artclaw_startup.py"
    )
    
    if doesFileExist pyStartup then (
        format "ArtClaw: Loading Python startup from: %\n" pyStartup
        python.ExecuteFile pyStartup
    ) else (
        format "ArtClaw: WARNING - artclaw_startup.py not found\n"
    )
)
