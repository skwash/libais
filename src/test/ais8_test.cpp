// Test parsing AIS 8 binary broadcast messages (BBM).

#include <memory>

#include "ais.h"
#include "gtest/gtest.h"

namespace libais {
namespace {

void ValidateAis8(const Ais8 *msg, const int repeat_indicator, const int mmsi,
                  const int spare,
                  const int dac, const int fi) {
  ASSERT_NE(nullptr, msg);
  EXPECT_FALSE(msg->had_error());

  ASSERT_EQ(8, msg->message_id);
  EXPECT_EQ(repeat_indicator, msg->repeat_indicator);
  EXPECT_EQ(mmsi, msg->mmsi);
  EXPECT_EQ(spare, msg->spare);

  EXPECT_EQ(dac, msg->dac);
  ASSERT_EQ(fi, msg->fi);
}

void ValidateAis8_1_11(
    const Ais8_1_11 *msg,
    // TODO(schwehr): position.
    const int day, const int hour, const int minute, const int wind_ave,
    const int wind_gust, const int wind_dir, const int wind_gust_dir,
    const float air_temp, const int rel_humid, const float dew_point,
    const float air_pres, const int air_pres_trend, const float horz_vis,
    const float water_level, const int water_level_trend,
    const float surf_cur_speed, const int surf_cur_dir, const float cur_speed_2,
    const int cur_dir_2, const int cur_depth_2, const float cur_speed_3,
    const int cur_dir_3, const int cur_depth_3, const float wave_height,
    const int wave_period, const int wave_dir, const float swell_height,
    const int swell_period, const int swell_dir, const int sea_state,
    const float water_temp, const int precip_type, const float salinity,
    const int ice, const int spare2, const int extended_water_level) {
  ASSERT_NE(nullptr, msg);
  // TODO(schwehr): AisPoint position;
  EXPECT_EQ(day, msg->day);
  EXPECT_EQ(hour, msg->hour);
  EXPECT_EQ(minute, msg->minute);
  EXPECT_EQ(wind_ave, msg->wind_ave);
  EXPECT_EQ(wind_gust, msg->wind_gust);
  EXPECT_EQ(wind_dir, msg->wind_dir);
  EXPECT_EQ(wind_gust_dir, msg->wind_gust_dir);
  EXPECT_FLOAT_EQ(air_temp, msg->air_temp);
  EXPECT_EQ(rel_humid, msg->rel_humid);
  EXPECT_FLOAT_EQ(dew_point, msg->dew_point);
  EXPECT_FLOAT_EQ(air_pres, msg->air_pres);
  EXPECT_EQ(air_pres_trend, msg->air_pres_trend);
  EXPECT_FLOAT_EQ(horz_vis, msg->horz_vis);
  EXPECT_FLOAT_EQ(water_level, msg->water_level);
  EXPECT_EQ(water_level_trend, msg->water_level_trend);
  EXPECT_FLOAT_EQ(surf_cur_speed, msg->surf_cur_speed);
  EXPECT_EQ(surf_cur_dir, msg->surf_cur_dir);
  EXPECT_FLOAT_EQ(cur_speed_2, msg->cur_speed_2);
  EXPECT_EQ(cur_dir_2, msg->cur_dir_2);
  EXPECT_EQ(cur_depth_2, msg->cur_depth_2);
  EXPECT_FLOAT_EQ(cur_speed_3, msg->cur_speed_3);
  EXPECT_EQ(cur_dir_3, msg->cur_dir_3);
  EXPECT_EQ(cur_depth_3, msg->cur_depth_3);
  EXPECT_FLOAT_EQ(wave_height, msg->wave_height);
  EXPECT_EQ(wave_period, msg->wave_period);
  EXPECT_EQ(wave_dir, msg->wave_dir);
  EXPECT_FLOAT_EQ(swell_height, msg->swell_height);
  EXPECT_EQ(swell_period, msg->swell_period);
  EXPECT_EQ(swell_dir, msg->swell_dir);
  EXPECT_EQ(sea_state, msg->sea_state);
  EXPECT_FLOAT_EQ(water_temp, msg->water_temp);
  EXPECT_EQ(precip_type, msg->precip_type);
  EXPECT_FLOAT_EQ(salinity, msg->salinity);
  EXPECT_EQ(ice, msg->ice);
  EXPECT_EQ(spare2, msg->spare2);
  EXPECT_EQ(extended_water_level, msg->extended_water_level);
}

// International Maritime Organization (IMO) Circ 289 meteorology and hydrography.
TEST(Ais8_1_11Test, DecodeAnything) {
  // clang-format off
  // !AIVDM,1,1,,A,8@2<HV@0BkLN:0frqMPaQPtBRRIrwwejwwwwwwwwwwwwwwwwwwwwwwwwwt0,2*34  // NOLINT
  // clang-format on
  std::unique_ptr<Ais8_1_11> msg(new Ais8_1_11(
      "8@2<HV@0BkLN:0frqMPaQPtBRRIrwwejwwwwwwwwwwwwwwwwwwwwwwwwwt0", 2));

  ValidateAis8(msg.get(), 1, 2300057, 0, 1, 11);
  ValidateAis8_1_11(msg.get(), /* TODO(schwehr): Position. */ 22, 1, 19, 6, 7,
                    274, 276, 1.5, 87, 82.3, 1020, 2, 25.5, 41.1, 3, 25.5, 511,
                    25.5, 511, 31, 25.5, 511, 31, 25.5, 63, 511, 25.5, 63, 511,
                    15, 92.3, 7, 51.1, 3, 0, 0);
}

TEST(Ais8_1_11Test, IncorrectBitCount) {
  std::unique_ptr<Ais8_1_11> msg(new Ais8_1_11(
      "8@2<HV@0BkLN:0frqMPaQPtBRRIrwwejwwwwwwwwwwwwwwwwwwwwwwwwwt0", 0));
  EXPECT_TRUE(msg->had_error());
}

// ITU-R M.1371-4 Annex 5 Table 25: text telegram with a 2-bit spare.
TEST(Ais8_1_0Test, SpareAfterText) {
  // Built by hand.  Each field has a distinct value.
  std::unique_ptr<Ais8_1_0> msg(new Ais8_1_0("85M:Ih00@<lfH2kSm4h", 2));

  ValidateAis8(msg.get(), 0, 366123456, 0, 1, 0);
  EXPECT_TRUE(msg->ack_required);
  EXPECT_EQ(1234, msg->msg_seq);
  EXPECT_EQ("9 KNOTS", msg->text);
  // The first 2 bits of the text are 11.  The spare after the text is 00.
  EXPECT_EQ(0, msg->spare2);
}

// IMO SN.1/Circ.289 Table 6.1 and 6.2: VTS-generated/synthetic targets.
TEST(Ais8_1_17Test, TwoTargets) {
  // Built by hand.  Each field has a distinct value.
  std::unique_ptr<Ais8_1_17> msg(new Ais8_1_17(
      "803OtPh0DIL@?7;?@2K`t=wGU1se38d48?7;<2Hq:>0gN4d77P", 4));

  ValidateAis8(msg.get(), 0, 3669123, 0, 1, 17);
  ASSERT_EQ(2, msg->targets.size());

  EXPECT_EQ(2, msg->targets[0].type);
  EXPECT_EQ("WDC1234", msg->targets[0].id);
  EXPECT_EQ(0, msg->targets[0].spare);
  EXPECT_DOUBLE_EQ(-70.25, msg->targets[0].position.lng_deg);
  EXPECT_DOUBLE_EQ(42.5, msg->targets[0].position.lat_deg);
  EXPECT_EQ(123, msg->targets[0].cog);
  EXPECT_EQ(45, msg->targets[0].timestamp);
  EXPECT_EQ(12, msg->targets[0].sog);

  EXPECT_EQ(2, msg->targets[1].type);
  EXPECT_EQ("KABC123", msg->targets[1].id);
  EXPECT_EQ(0, msg->targets[1].spare);
  EXPECT_DOUBLE_EQ(-69.5, msg->targets[1].position.lng_deg);
  EXPECT_DOUBLE_EQ(41.75, msg->targets[1].position.lat_deg);
  EXPECT_EQ(300, msg->targets[1].cog);
  EXPECT_EQ(7, msg->targets[1].timestamp);
  EXPECT_EQ(30, msg->targets[1].sog);
}

TEST(Ais8_1_17Test, NoTargets) {
  // Target 1 is mandatory.  The header alone is 56 bits.
  std::unique_ptr<Ais8_1_17> msg(new Ais8_1_17("803OtPh0D@", 4));
  EXPECT_TRUE(msg->had_error());
  EXPECT_EQ(AIS_ERR_BAD_BIT_COUNT, msg->get_error());
}

}  // namespace
}  // namespace libais
