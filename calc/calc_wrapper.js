#!/usr/bin/env node
/**
 * Node.js wrapper for @smogon/calc damage calculator.
 * Reads JSON from stdin, performs calculation, outputs JSON to stdout.
 */

const { calculate, Generations, Pokemon, Move, Field } = require("@smogon/calc");

// Get Gen 9 for VGC 2026
const gen = Generations.get(9);

/**
 * Parse EV object from input format.
 * Accepts: {hp: 252, atk: 0, ...} or defaults to 0s
 */
function parseEVs(evs) {
  if (!evs) return { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
  return {
    hp: evs.hp || 0,
    atk: evs.atk || 0,
    def: evs.def || 0,
    spa: evs.spa || 0,
    spd: evs.spd || 0,
    spe: evs.spe || 0,
  };
}

/**
 * Parse IV object from input format.
 * Accepts: {hp: 31, atk: 31, ...} or defaults to 31s
 */
function parseIVs(ivs) {
  if (!ivs) return { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 };
  return {
    hp: ivs.hp ?? 31,
    atk: ivs.atk ?? 31,
    def: ivs.def ?? 31,
    spa: ivs.spa ?? 31,
    spd: ivs.spd ?? 31,
    spe: ivs.spe ?? 31,
  };
}

/**
 * Parse boost object.
 */
function parseBoosts(boosts) {
  if (!boosts) return {};
  return {
    atk: boosts.atk || 0,
    def: boosts.def || 0,
    spa: boosts.spa || 0,
    spd: boosts.spd || 0,
    spe: boosts.spe || 0,
  };
}

/**
 * Build a Pokemon object from input data.
 */
function buildPokemon(data) {
  if (!data || !data.name) {
    throw new Error("Pokemon name is required");
  }

  const options = {
    level: data.level || 50,
    evs: parseEVs(data.evs),
    ivs: parseIVs(data.ivs),
    boosts: parseBoosts(data.boosts),
  };

  if (data.nature) options.nature = data.nature;
  if (data.item) options.item = data.item;
  if (data.ability) options.ability = data.ability;
  if (data.teraType) options.teraType = data.teraType;
  if (data.status) options.status = data.status;
  if (data.curHP !== undefined) options.curHP = data.curHP;
  if (data.isBurned) options.status = "Burned";
  if (data.isParalyzed) options.status = "Paralyzed";

  return new Pokemon(gen, data.name, options);
}

/**
 * Build a Field object from input data.
 */
function buildField(data) {
  if (!data) {
    return new Field({ gameType: "Doubles" });
  }

  const fieldOptions = {
    gameType: data.gameType || "Doubles",
  };

  if (data.weather) fieldOptions.weather = data.weather;
  if (data.terrain) fieldOptions.terrain = data.terrain;
  if (data.isGravity) fieldOptions.isGravity = true;
  if (data.isMagicRoom) fieldOptions.isMagicRoom = true;
  if (data.isWonderRoom) fieldOptions.isWonderRoom = true;
  if (data.isAuraBreak) fieldOptions.isAuraBreak = true;
  if (data.isFairyAura) fieldOptions.isFairyAura = true;
  if (data.isDarkAura) fieldOptions.isDarkAura = true;
  if (data.isBeadsOfRuin) fieldOptions.isBeadsOfRuin = true;
  if (data.isSwordOfRuin) fieldOptions.isSwordOfRuin = true;
  if (data.isTabletsOfRuin) fieldOptions.isTabletsOfRuin = true;
  if (data.isVesselOfRuin) fieldOptions.isVesselOfRuin = true;

  // Attacker side conditions
  if (data.attackerSide) {
    fieldOptions.attackerSide = {};
    const as = data.attackerSide;
    if (as.isHelpingHand) fieldOptions.attackerSide.isHelpingHand = true;
    if (as.isTailwind) fieldOptions.attackerSide.isTailwind = true;
    if (as.isFlowerGift) fieldOptions.attackerSide.isFlowerGift = true;
    if (as.isPowerSpot) fieldOptions.attackerSide.isPowerSpot = true;
    if (as.isBattery) fieldOptions.attackerSide.isBattery = true;
    if (as.steelySpirit) fieldOptions.attackerSide.steelySpirit = as.steelySpirit;
  }

  // Defender side conditions
  if (data.defenderSide) {
    fieldOptions.defenderSide = {};
    const ds = data.defenderSide;
    if (ds.isReflect) fieldOptions.defenderSide.isReflect = true;
    if (ds.isLightScreen) fieldOptions.defenderSide.isLightScreen = true;
    if (ds.isAuroraVeil) fieldOptions.defenderSide.isAuroraVeil = true;
    if (ds.isFriendGuard) fieldOptions.defenderSide.isFriendGuard = true;
    if (ds.isProtected) fieldOptions.defenderSide.isProtected = true;
    if (ds.spikes) fieldOptions.defenderSide.spikes = ds.spikes;
    if (ds.isSR) fieldOptions.defenderSide.isSR = true;
  }

  return new Field(fieldOptions);
}

/**
 * Build a Move object from input data.
 */
function buildMove(data, attacker) {
  if (typeof data === "string") {
    return new Move(gen, data);
  }

  const options = {};
  if (data.isCrit) options.isCrit = true;
  if (data.hits) options.hits = data.hits;
  if (data.isSpread !== undefined) options.isSpread = data.isSpread;
  if (data.useZ) options.useZ = true;
  if (data.useMax) options.useMax = true;
  if (data.overrides) options.overrides = data.overrides;

  return new Move(gen, data.name || data, options);
}

/**
 * Extract KO chance description from result.
 */
function getKOChance(result) {
  const ko = result.kpiS();
  if (!ko) return null;

  // Try to get a readable KO chance
  try {
    const desc = result.fullDesc();
    // Extract the KO chance part (e.g., "87.5% chance to OHKO")
    const match = desc.match(/(\d+(?:\.\d+)?% chance to \d?HKO|guaranteed \d?HKO|\d?HKO)/i);
    if (match) return match[0];
  } catch (e) {
    // Ignore errors
  }

  return null;
}

/**
 * Perform the damage calculation.
 */
function calculateDamage(input) {
  try {
    const attacker = buildPokemon(input.attacker);
    const defender = buildPokemon(input.defender);
    const move = buildMove(input.move, attacker);
    const field = buildField(input.field);

    const result = calculate(gen, attacker, defender, move, field);

    // Get damage rolls
    const damage = result.damage;
    let damageArray;
    if (Array.isArray(damage)) {
      if (Array.isArray(damage[0])) {
        // Multi-hit move
        damageArray = damage[0];
      } else {
        damageArray = damage;
      }
    } else {
      damageArray = [damage];
    }

    // Calculate defender's max HP
    const defenderMaxHP = defender.maxHP();

    // Get min/max damage
    const minDamage = Math.min(...damageArray);
    const maxDamage = Math.max(...damageArray);

    // Calculate percentages
    const minPercent = (minDamage / defenderMaxHP) * 100;
    const maxPercent = (maxDamage / defenderMaxHP) * 100;

    // Get full description
    let description;
    try {
      description = result.fullDesc();
    } catch (e) {
      description = result.moveDesc();
    }

    // Determine KO chance
    let koChance = null;
    if (minPercent >= 100) {
      koChance = "guaranteed OHKO";
    } else if (maxPercent >= 100) {
      // Calculate actual probability
      const ohkoRolls = damageArray.filter((d) => d >= defenderMaxHP).length;
      const percent = ((ohkoRolls / damageArray.length) * 100).toFixed(1);
      koChance = `${percent}% chance to OHKO`;
    } else if (maxPercent >= 50) {
      koChance = `${minPercent.toFixed(1)}-${maxPercent.toFixed(1)}% (possible 2HKO)`;
    }

    return {
      success: true,
      damage: damageArray,
      minDamage,
      maxDamage,
      defenderMaxHP,
      minPercent: parseFloat(minPercent.toFixed(1)),
      maxPercent: parseFloat(maxPercent.toFixed(1)),
      koChance,
      description,
      attacker: {
        name: attacker.name,
        types: attacker.types,
        stats: {
          hp: attacker.rawStats.hp,
          atk: attacker.rawStats.atk,
          def: attacker.rawStats.def,
          spa: attacker.rawStats.spa,
          spd: attacker.rawStats.spd,
          spe: attacker.rawStats.spe,
        },
      },
      defender: {
        name: defender.name,
        types: defender.types,
        stats: {
          hp: defender.rawStats.hp,
          atk: defender.rawStats.atk,
          def: defender.rawStats.def,
          spa: defender.rawStats.spa,
          spd: defender.rawStats.spd,
          spe: defender.rawStats.spe,
        },
      },
      move: {
        name: move.name,
        type: move.type,
        category: move.category,
        bp: move.bp,
      },
    };
  } catch (error) {
    return {
      success: false,
      error: error.message,
    };
  }
}

/**
 * Main: Read JSON from stdin, process, output to stdout.
 */
async function main() {
  let input = "";

  // Read from stdin
  for await (const chunk of process.stdin) {
    input += chunk;
  }

  try {
    const data = JSON.parse(input);

    // Handle batch calculations
    if (Array.isArray(data)) {
      const results = data.map(calculateDamage);
      console.log(JSON.stringify(results));
    } else {
      const result = calculateDamage(data);
      console.log(JSON.stringify(result));
    }
  } catch (error) {
    console.log(
      JSON.stringify({
        success: false,
        error: `Failed to parse input: ${error.message}`,
      })
    );
    process.exit(1);
  }
}

main();
