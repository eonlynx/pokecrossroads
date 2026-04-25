#include "global.h"
#include "constants/trainers.h"

static enum TrainerPicID GetEmeraldTrainerPic(enum Gender gender)
{
    return gender == MALE ? TRAINER_PIC_BRENDAN : TRAINER_PIC_MAY;
}
static enum TrainerPicID GetRSTrainerPic(enum Gender gender)
{
    return gender == MALE ? TRAINER_PIC_RS_BRENDAN : TRAINER_PIC_RS_MAY;
}

static enum TrainerPicID GetKantoTrainerPic(enum Gender gender)
{
    return gender == MALE ? TRAINER_PIC_RED : TRAINER_PIC_LEAF;
}

enum TrainerPicID GetPlayerTrainerPic(enum Gender gender, enum GameVersion version)
{
    if (gSaveBlock2Ptr->playerRegion == REGION_KANTO)
        return GetKantoTrainerPic(gender);
    else if (version == VERSION_SAPPHIRE || version == VERSION_RUBY)
        return GetRSTrainerPic(gender);
    else
        return GetEmeraldTrainerPic(gender);
}
