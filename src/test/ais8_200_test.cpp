// Test parsing EU River Information System (RIS) 8:200:* messages.

#include <array>
#include <memory>
#include <string>

#include "ais.h"
#include "gtest/gtest.h"

namespace libais {
namespace {

// TODO(schwehr): Test eu_id.
void Validate8_200_10(const Ais8_200_10 *msg, const int repeat_indicator,
                      const int mmsi, const std::string & /* eu_id */,
                      const float length, const float beam, const int ship_type,
                      const int haz_cargo, const float draught,
                      const int loaded, const int speed_qual,
                      const int course_qual, const int heading_qual,
                      const int spare2) {
  ASSERT_NE(nullptr, msg);
  EXPECT_FALSE(msg->had_error());

  ASSERT_EQ(8, msg->message_id);
  EXPECT_EQ(repeat_indicator, msg->repeat_indicator);
  EXPECT_EQ(mmsi, msg->mmsi);
  EXPECT_EQ(200, msg->dac);
  ASSERT_EQ(10, msg->fi);

  EXPECT_FLOAT_EQ(length, msg->length);
  EXPECT_FLOAT_EQ(beam, msg->beam);
  EXPECT_EQ(ship_type, msg->ship_type);
  EXPECT_EQ(haz_cargo, msg->haz_cargo);
  EXPECT_FLOAT_EQ(draught, msg->draught);
  EXPECT_EQ(loaded, msg->loaded);
  EXPECT_EQ(speed_qual, msg->speed_qual);
  EXPECT_EQ(course_qual, msg->course_qual);
  EXPECT_EQ(heading_qual, msg->heading_qual);
  EXPECT_EQ(spare2, msg->spare2);
}

TEST(Ais8_200_10Test, DecodeAnything) {
  // clang-format off
  // !SAVDM,1,1,5,B,85NLn@0j2d<8000000BhI?`50000,0*2A,d,S1241,t002333.00,T33.111314,D08MN-NO-BSABS1,1429316613 NOLINT
  // clang-format on

  std::unique_ptr<Ais8_200_10> msg(
      new Ais8_200_10("85NLn@0j2d<8000000BhI?`50000", 0));
  Validate8_200_10(msg.get(), 0, 367474240, std::string("foo"), 15, 5, 8000, 5,
                   0, 0, 0, 0, 0, 0);
}

// ES-RIS Edition 2023/1 Annex 11 Table 11-4: ETA at lock/bridge/terminal.
TEST(Ais8_200_21Test, EtaReport) {
  // Built by hand.  Each field has a distinct value.  Bits 56-87 are zero.
  std::unique_ptr<Ais8_200_21> msg(
      new Ais8_200_21("832S7Thj5@000005AHTG37;?@ht<g737W;FueeBL@0", 4));
  ASSERT_NE(nullptr, msg);
  EXPECT_FALSE(msg->had_error());

  ASSERT_EQ(8, msg->message_id);
  EXPECT_EQ(203999123, msg->mmsi);
  EXPECT_EQ(200, msg->dac);
  ASSERT_EQ(21, msg->fi);

  EXPECT_EQ("AT", msg->country);
  EXPECT_EQ("VIE", msg->location);
  EXPECT_EQ("01234", msg->section);
  EXPECT_EQ("LOCK1", msg->terminal);
  EXPECT_EQ("01925", msg->hectometre);
  EXPECT_EQ(11, msg->eta_month);
  EXPECT_EQ(27, msg->eta_day);
  EXPECT_EQ(13, msg->eta_hour);
  EXPECT_EQ(45, msg->eta_minute);
  EXPECT_EQ(2, msg->tugboats);
  EXPECT_FLOAT_EQ(12.5, msg->air_draught);
  EXPECT_EQ(0, msg->spare2);
}

// ES-RIS Edition 2023/1 Annex 11 Table 11-8: RTA at lock/bridge/terminal.
TEST(Ais8_200_22Test, RtaReport) {
  // Built by hand.  Each field has a distinct value.  Bits 56-87 are zero.
  std::unique_ptr<Ais8_200_22> msg(
      new Ais8_200_22("801tPehj5P000005AHTG37;?@ht<g737W;Fuee@", 2));
  ASSERT_NE(nullptr, msg);
  EXPECT_FALSE(msg->had_error());

  ASSERT_EQ(8, msg->message_id);
  EXPECT_EQ(2039991, msg->mmsi);
  EXPECT_EQ(200, msg->dac);
  ASSERT_EQ(22, msg->fi);

  EXPECT_EQ("AT", msg->country);
  EXPECT_EQ("VIE", msg->location);
  EXPECT_EQ("01234", msg->section);
  EXPECT_EQ("LOCK1", msg->terminal);
  EXPECT_EQ("01925", msg->hectometre);
  EXPECT_EQ(11, msg->rta_month);
  EXPECT_EQ(27, msg->rta_day);
  EXPECT_EQ(13, msg->rta_hour);
  EXPECT_EQ(45, msg->rta_minute);
  EXPECT_EQ(1, msg->lock_status);
  EXPECT_EQ(0, msg->spare2);
}

void Validate8_200_24(const Ais8_200_24 &msg, const int repeat_indicator,
                      const int mmsi, const std::string country,
                      std::array<int, 4> gauge_ids,
                      std::array<float, 4> levels) {
  EXPECT_FALSE(msg.had_error());

  ASSERT_EQ(8, msg.message_id);
  ASSERT_EQ(repeat_indicator, msg.repeat_indicator);
  EXPECT_EQ(mmsi, msg.mmsi);
  EXPECT_EQ(200, msg.dac);
  ASSERT_EQ(24, msg.fi);

  EXPECT_EQ(country, msg.country);
  for (int i = 0; i < 4; i++) {
    EXPECT_EQ(gauge_ids[i], msg.gauge_ids[i]);
  }
  for (int i = 0; i < 4; i++) {
    EXPECT_FLOAT_EQ(levels[i], msg.levels[i]);
  }
}

TEST(Ais8_200_24, Issue162) {
  // 8:200:24 EU River Information System (RIS) Water level
  // https://github.com/schwehr/libais/issues/162
  /*
     \s:rORBCOMM000,q:u,c:1510617616,T:2017-11-14 00.00.16*5f\
         !AIVDM,1,1,,A,801tME0j60E04QJp1hhL10G20DH1,0*11
  */
  std::unique_ptr<Ais8_200_24> msg(
      new Ais8_200_24("801tME0j60E04QJp1hhL10G20DH1", 0));
  ASSERT_NE(nullptr, msg);
  constexpr float level = 4294966528.0f;
  Validate8_200_24(*msg, 0, 2039124, "AT", {9, 7, 8, 5},
                   {level, level, level, level});

  // !AIVDM,1,1,,B,802ATu0j624P2@G80pEd0D5F0634,0*2F
  msg.reset(new Ais8_200_24("802ATu0j624P2@G80pEd0D5F0634", 0));
  Validate8_200_24(*msg, 0, 2385140, "HR", {4, 3, 2, 1},
                   {185.0f, 347.0f, 171.0f, 196.0f});
}

}  // namespace
}  // namespace libais
