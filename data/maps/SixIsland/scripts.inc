SixIsland_MapScripts::
	map_script MAP_SCRIPT_ON_TRANSITION, SixIsland_OnTransition
	.byte 0

SixIsland_OnTransition:
	setflag FLAG_WORLD_MAP_SIX_ISLAND
	end

SixIsland_EventScript_IslandSign::
	msgbox SixIsland_Text_IslandSign, MSGBOX_SIGN
	end

SixIsland_Text_IslandSign::
    .string "SIX ISLAND\n"
    .string "Fortune Island of Aged Wisdom$"
