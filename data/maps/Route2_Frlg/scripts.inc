Route2_Frlg_MapScripts::
	.byte 0

Route2_EventScript_RouteSign::
	msgbox Route2_Text_RouteSign, MSGBOX_SIGN
	end

Route2_EventScript_DiglettsCaveSign::
	msgbox Route2_Text_DiglettsCave, MSGBOX_SIGN
	end

Route2_Text_RouteSign::
	.string "ROUTE 2\n"
	.string "VIRIDIAN CITY - PEWTER CITY$"

Route2_Text_DiglettsCave::
	.string "DIGLETT'S CAVE$"

Route2_EventScript_ProfBirchAssistant::
	lock
	faceplayer
	checkflag FLAG_GOT_FLIGHT_CALL
	goto_if TRUE, Route2_EventScript_ProfBirchAssistant_Done

	msgbox Route2_Text_Hoenn, MSGBOX_DEFAULT
	giveitem ITEM_FLIGHT_CALL, 1
	setflag FLAG_VISITED_LITTLEROOT_TOWN
	setflag FLAG_GOT_FLIGHT_CALL
	msgbox Route2_Text_ReceivedDevice, MSGBOX_DEFAULT
	msgbox Route2_Text_HoennAfterGift, MSGBOX_DEFAULT
	closemessage
	applymovement ProfBirchAssistant, Route2_Movement_ProfBirchAssistantWarpOut
	waitmovement 0
	setflag FLAG_HIDE_ROUTE_PROF_ASSISTANT
	hideobjectat ProfBirchAssistant, MAP_ROUTE2
	releaseall
	end

Route2_EventScript_ProfBirchAssistant_Done::
	releaseall
	end

Route2_Text_Hoenn:
	.string "{PLAYER}!!!\n"
	.string "Prof Oak said you'd be coming\l"
	.string "through here.\p"
	.string "Prof Birch in Hoenn wanted\n"
	.string "me to find you.\p"
	.string "He wants you to have this.$"

Route2_Text_ReceivedDevice:
	.string "{PLAYER} received the new\n"
	.string "Flight Call device!$"

Route2_Text_HoennAfterGift:
	.string "That device should enable you\n"
	.string "to visit Hoenn.\p"
	.string "I should get back to the lab\n"
	.string "myself. See you later!$"

Route2_Movement_ProfBirchAssistantWarpOut:
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	walk_left
	set_invisible
	step_end
