#ifndef GUARD_POKEDEX_AREA_SCREEN_H
#define GUARD_POKEDEX_AREA_SCREEN_H

#include "rtc.h"

extern u8 gAreaTimeOfDay;

enum PokedexAreaScreenState
{
    DEX_SHOW_AREA_SCREEN,
    DEX_UPDATE_AREA_SCREEN
};

void DisplayPokedexAreaScreen(u16 species, u8 *screenSwitchState, u8 mapNum, enum TimeOfDay timeOfDay, enum PokedexAreaScreenState areaState);

#endif // GUARD_POKEDEX_AREA_SCREEN_H
